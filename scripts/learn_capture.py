#!/usr/bin/env python3
"""Hook capture: the opt-in trigger that hands a session's signals to `learn`.

docs/LEARNING.md ("Hook capture" and "The capture A/B") is the normative
description; this module is its executable half. A capture hook is a trigger,
not a drafter. A `crew-proposal/1` draft needs a judged classification and a
diff, which a deterministic hook cannot write, so at the end of a turn the hook
asks the session's own agent to run `learn` on the signals it counted. Every
draft therefore goes through `learn` and its gates, into the declared queue.

The hook reads harness events, never session text into its output: it records
signal kinds, counts and hashed keys, and its continuation prompt names counts
only. Tool output, a prompt or a denial reason never reaches the prompt it
writes, so a planted line cannot become an instruction by way of the hook.

    learn_capture.py --hook --harness claude|codex|pi   < event JSON
    learn_capture.py --report CONSUMER_ROOT [--format json|markdown]

`--hook` always exits 0. It writes only `<queue>/capture/sessions/*.json`, and
nothing at all when the project declares no queue. At a turn's end in the
capture arm it may print `{"decision": "block", "reason": ...}`, the Stop
continuation Claude Code and Codex share; the pi extension translates it.
`--report` is read-only and prints the A/B metrics. Stdlib only.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any

try:
    import fcntl
except ImportError:  # Not POSIX: hooks still run, without the record lock.
    fcntl = None  # type: ignore[assignment]

try:
    from .learn_contract import (
        HARNESSES, find_project_root, queue_location, queue_location_errors, read_proposal, sections, _split,
    )
except ImportError:  # Direct script execution.
    from learn_contract import (
        HARNESSES, find_project_root, queue_location, queue_location_errors, read_proposal, sections, _split,
    )


SESSION_SCHEMA = "crew-capture-session/1"
CREW_ROOT = pathlib.Path(__file__).resolve().parent.parent
ARMS = ("baseline", "capture")
SIGNAL_KINDS = ("repeated-failure", "denial", "correction")

# A failure qualifies once the same call has failed this often in one session.
REPEAT = 2
# Opening words of an operator turn that read as a correction. A heuristic, so
# its signals are candidates the agent confirms, never facts.
CORRECTION = re.compile(
    r"^\W*(?:no\b|nope\b|don'?t\b|do not\b|stop\b|wrong\b|wait\b|undo\b|revert\b|actually\b|instead\b"
    r"|that'?s (?:not|wrong)\b|that is (?:not|wrong)\b|why did you\b|you (?:shouldn'?t|should not|didn'?t|did not)\b)",
    re.IGNORECASE,
)
EXIT_CODE = re.compile(r"^\s*Exit code:?\s*(-?\d+)", re.IGNORECASE)
SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")
CONTINUATION_OPENING = "Crew capture (docs/LEARNING.md, Hook capture):"
LESSON_TEST = re.compile(r"^lesson-test:[ \t]*(pass|fail)\b", re.MULTILINE)


def crew_version() -> str:
    try:
        return json.loads((CREW_ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return ""


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


def _digest(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:12]


def assign_arm(session_id: str) -> str:
    """Split sessions between the arms by a hash of their id: stable for a session."""
    return ARMS[int(hashlib.sha256(session_id.encode()).hexdigest()[:8], 16) % 2]


# ------------------------------------------------------------------ the queue


def resolve_queue(cwd: str | os.PathLike[str]) -> tuple[pathlib.Path, pathlib.Path] | None:
    """(project root, queue) when the project declares a usable queue; None means do nothing."""
    root = find_project_root(pathlib.Path(cwd))
    if root is None:
        return None
    try:
        location = queue_location((root / "AGENTS.md").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    if location is None or queue_location_errors(location):
        return None
    return root, root / location


def proposal_ids(queue: pathlib.Path) -> list[str]:
    return sorted(
        path.stem for path in queue.glob("*.md") if path.name.upper() not in {"README.MD", "SKILL.MD"}
    )


def committed_ids(root: pathlib.Path, queue: pathlib.Path) -> set[str]:
    """Proposal ids tracked in the project's git HEAD: a pull or branch switch, not a fresh draft."""
    try:
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "--name-only", "HEAD", "--", f"{queue.relative_to(root).as_posix()}/"],
            capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return set()
    if listed.returncode:
        return set()
    return {pathlib.PurePosixPath(line).stem for line in listed.stdout.splitlines() if line.endswith(".md")}


def sessions_dir(queue: pathlib.Path) -> pathlib.Path:
    return queue / "capture" / "sessions"


# ------------------------------------------------------------------- signals


def tool_failed(event: dict[str, Any]) -> bool:
    """Whether a tool event reports a failure. PostToolUseFailure always does.

    Codex documents `tool_response` only as tool-specific output, so a
    PostToolUse is read as failed when it carries a non-zero exit code or an
    error flag, as a field or as the `Exit code: N` line its model-facing output
    opens with. Anything else is not a failure.
    """
    if event.get("is_interrupt"):
        return False
    if event.get("hook_event_name") == "PostToolUseFailure":
        return True
    response = event.get("tool_response")
    if isinstance(response, dict):
        for key in ("exit_code", "exitCode"):
            if isinstance(response.get(key), int) and response[key] != 0:
                return True
        if response.get("is_error") is True or response.get("isError") is True or response.get("success") is False:
            return True
        response = response.get("output", response.get("stdout"))
    if isinstance(response, str):
        match = EXIT_CODE.match(response)
        return bool(match and int(match.group(1)) != 0)
    return False


def record_signal(record: dict[str, Any], kind: str, key: str) -> None:
    signal = record["signals"].setdefault(
        key, {"kind": kind, "count": 0, "handed": False, "continuation": record["pending-trigger"]},
    )
    signal["count"] += 1
    if record["pending-trigger"]:  # `learn`'s own run, which the hook asked for, is not a signal.
        signal["handed"] = True


def qualifying(record: dict[str, Any]) -> list[str]:
    """Signal keys worth a `learn` pass that no earlier trigger handed over."""
    keys = []
    for key, signal in record["signals"].items():
        if signal["handed"]:
            continue
        if signal["kind"] == "repeated-failure" and signal["count"] < REPEAT:
            continue
        keys.append(key)
    return keys


def continuation(record: dict[str, Any], keys: list[str]) -> str:
    """The prompt the agent continues with: counts and kinds only, never session text."""
    counts = {kind: 0 for kind in SIGNAL_KINDS}
    for key in keys:
        counts[record["signals"][key]["kind"]] += 1
    named = {
        "repeated-failure": "tool call(s) that failed more than once",
        "denial": "denied tool call(s)",
        "correction": "operator turn(s) that read like a correction",
    }
    found = "; ".join(f"{count} {named[kind]}" for kind, count in counts.items() if count)
    return (
        f"{CONTINUATION_OPENING} this session recorded learning-signal "
        f"candidates since the last capture: {found}. Run the `learn` skill's experience source "
        "on them now: find each moment in this session yourself, drop candidates as its section 2b "
        "says, and draft any lesson that survives into the declared proposal queue through every "
        "gate. If none survives, say `no lessons` in one line and stop. Drafts only: apply nothing."
    )


# ------------------------------------------------------------------- the hook


def new_record(event: dict[str, Any], harness: str, queue: pathlib.Path) -> dict[str, Any]:
    session_id = str(event["session_id"])
    return {
        "schema": SESSION_SCHEMA,
        "session": session_id,
        "harness": harness,
        "arm": assign_arm(session_id),
        "crew": crew_version(),
        "started": now(),
        "opened-by": event.get("hook_event_name", ""),
        "queue-at-start": proposal_ids(queue),
        "prompts": 0,
        "signals": {},
        "triggers": [],
        "pending-trigger": False,
        "proposals": {},
    }


def apply_event(
    record: dict[str, Any], event: dict[str, Any], root: pathlib.Path, queue: pathlib.Path,
) -> dict[str, Any] | None:
    """Update a session record for one event; return the Stop output, if any."""
    name = event.get("hook_event_name")
    record["updated"] = now()
    if name == "UserPromptSubmit":
        record["prompts"] += 1
        prompt = event.get("prompt")
        if not (isinstance(prompt, str) and prompt.startswith(CONTINUATION_OPENING)):
            record["pending-trigger"] = False
        if record["prompts"] > 1 and isinstance(prompt, str) and CORRECTION.match(prompt):
            record_signal(record, "correction", f"correction-{record['prompts']}")
    elif name in {"PostToolUse", "PostToolUseFailure"} and tool_failed(event):
        record_signal(record, "repeated-failure",
                      "failure-" + _digest(event.get("tool_name"), event.get("tool_input")))
    elif name == "PermissionDenied":
        record_signal(record, "denial", "denial-" + _digest(event.get("tool_name"), event.get("tool_input")))
    elif name == "Stop":
        return stop(record, event, root, queue)
    return None


def stop(
    record: dict[str, Any], event: dict[str, Any], root: pathlib.Path, queue: pathlib.Path,
) -> dict[str, Any] | None:
    """Attribute new proposals, then trigger `learn` once per batch of new signals."""
    trigger = "capture" if record["pending-trigger"] else "session"
    known = set(record["queue-at-start"]) | set(record["proposals"])
    new = [proposal for proposal in proposal_ids(queue) if proposal not in known]
    if new:
        committed = committed_ids(root, queue)
        for proposal in new:
            if proposal not in committed:
                record["proposals"][proposal] = trigger
    record["pending-trigger"] = False
    if record["arm"] != "capture" or event.get("stop_hook_active"):
        return None
    keys = qualifying(record)
    if not keys:
        return None
    for key in keys:
        record["signals"][key]["handed"] = True
    record["triggers"].append({"at": now(), "signals": len(keys)})
    record["pending-trigger"] = True
    return {"decision": "block", "reason": continuation(record, keys)}


@contextlib.contextmanager
def locked_record(root: pathlib.Path, path: pathlib.Path):
    """Open a session record under an exclusive lock; tool hooks can run in parallel.

    The queue is committed project content, so a hostile checkout could plant a
    symlink in it to aim this write outside the project. No component below the
    project root, nor the record itself, may be a symlink.
    """
    directory = root
    for part in path.relative_to(root).parent.parts:
        directory = directory / part
        if directory.is_symlink():
            raise OSError(f"{directory} is a symlink; capture writes only inside the project")
        directory.mkdir(exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(os.dup(fd), "r+", encoding="utf-8") as handle:
            yield handle
    finally:
        os.close(fd)


def handle_event(event: dict[str, Any], *, harness: str) -> dict[str, Any] | None:
    """One hook invocation. Returns the Stop output to print, or None."""
    session_id = event.get("session_id")
    cwd = event.get("cwd") or os.getcwd()
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    resolved = resolve_queue(cwd)
    if resolved is None:
        return None
    root, queue = resolved
    name = f"{harness}-{SAFE_ID.sub('-', session_id).strip('-.')[:96]}.json"
    with locked_record(root, sessions_dir(queue) / name) as handle:
        text = handle.read()
        try:
            record = json.loads(text) if text.strip() else None
        except ValueError:
            record = None
        if not isinstance(record, dict) or record.get("schema") != SESSION_SCHEMA:
            record = new_record(event, harness, queue)
        output = apply_event(record, event, root, queue)
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return output


def run_hook(harness: str, stdin: str) -> str:
    """Never fails the session: any error is swallowed and the hook prints nothing."""
    try:
        event = json.loads(stdin)
        if not isinstance(event, dict):
            return ""
        output = handle_event(event, harness=harness)
    except Exception:  # noqa: BLE001 - a learning aid must never break the session it observes.
        return ""
    return json.dumps(output) if output else ""


# ------------------------------------------------------------------ the report


def lesson_test(path: pathlib.Path) -> str | None:
    """`pass` or `fail` from a `lesson-test:` line under ## Review, if recorded."""
    try:
        split = _split(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    if split is None:
        return None
    match = LESSON_TEST.search("\n".join(sections(split[1]).get("Review", [])))
    return match.group(1) if match else None


def proposal_outcomes(queue: pathlib.Path) -> dict[str, dict[str, Any]]:
    outcomes: dict[str, dict[str, Any]] = {}
    for path in sorted(queue.glob("*.md")):
        if path.name.upper() in {"README.MD", "SKILL.MD"}:
            continue
        try:
            fields = read_proposal(path) or {}
        except (OSError, UnicodeDecodeError):
            fields = {}
        status = fields.get("status", "")
        promoted = status == "promoted" or bool(fields.get("promoted-in"))
        outcomes[path.stem] = {
            "status": status,
            "accepted": promoted or status == "reviewed",
            "promoted": promoted,
            "lesson-test": lesson_test(path),
        }
    return outcomes


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 3) if denominator else None


def build_report(consumer_root: pathlib.Path) -> dict[str, Any]:
    """The capture A/B: per-arm, per-session drafted, accepted, promoted and lesson-test rates."""
    resolved = resolve_queue(consumer_root)
    if resolved is None:
        return {"declared": False, "arms": {}, "note": "no usable proposal-queue declared; nothing to measure"}
    _, queue = resolved
    outcomes = proposal_outcomes(queue)
    records = []
    for path in sorted(sessions_dir(queue).glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and record.get("schema") == SESSION_SCHEMA and record.get("arm") in ARMS:
            records.append(record)

    # Each proposal counts once: the first record, in sorted order, that lists it.
    attributed: set[str] = set()
    owned: list[tuple[dict[str, Any], dict[str, str]]] = []
    for record in records:
        proposals = {
            proposal: trigger for proposal, trigger in record.get("proposals", {}).items() if proposal not in attributed
        }
        attributed.update(proposals)
        owned.append((record, proposals))

    arms: dict[str, Any] = {}
    for arm in ARMS:
        mine = [record for record, _ in owned if record["arm"] == arm]
        by_trigger: dict[str, dict[str, int]] = {}
        tests = {"pass": 0, "fail": 0}
        for record, proposals in owned:
            if record["arm"] != arm:
                continue
            for proposal, trigger in proposals.items():
                outcome = outcomes.get(proposal)
                counts = by_trigger.setdefault(trigger, {"drafted": 0, "accepted": 0, "promoted": 0})
                counts["drafted"] += 1
                if outcome is None:  # Deleted before review: drafted, never accepted.
                    continue
                counts["accepted"] += outcome["accepted"]
                counts["promoted"] += outcome["promoted"]
                if outcome["lesson-test"]:
                    tests[outcome["lesson-test"]] += 1
        total = {key: sum(counts[key] for counts in by_trigger.values()) for key in ("drafted", "accepted", "promoted")}
        sessions = len(mine)
        arms[arm] = {
            "sessions": sessions,
            "harnesses": sorted({record.get("harness", "") for record in mine}),
            "signals": sum(
                not signal.get("continuation") for record in mine for signal in record.get("signals", {}).values()
            ),
            "triggers": sum(len(record.get("triggers", [])) for record in mine),
            **total,
            "by-trigger": by_trigger,
            "per-session": {key: _rate(value, sessions) for key, value in total.items()},
            "lesson-tests": {**tests, "pass-rate": _rate(tests["pass"], tests["pass"] + tests["fail"])},
        }
    baseline, capture = arms["baseline"]["per-session"]["accepted"], arms["capture"]["per-session"]["accepted"]
    return {
        "declared": True,
        "queue": str(queue),
        "arms": arms,
        "unattributed": sorted(set(outcomes) - attributed),
        "accepted-per-session-difference": (
            round(capture - baseline, 3) if capture is not None and baseline is not None else None
        ),
        "decision-rule": "keep the capture hooks only if the capture arm's accepted lessons per session "
                         "exceed the baseline arm's; the operator decides, from real sessions",
    }


def render_markdown(report: dict[str, Any]) -> str:
    if not report["declared"]:
        return f"# Capture A/B\n\n{report['note']}\n"
    rows = [
        ("sessions", "sessions"), ("signals recorded", "signals"), ("capture triggers", "triggers"),
        ("proposals drafted", "drafted"), ("accepted", "accepted"), ("promoted", "promoted"),
    ]
    arms = report["arms"]
    lines = ["# Capture A/B", "", f"Queue: `{report['queue']}`", "", "| Metric | baseline | capture |", "|---|---|---|"]
    lines += [f"| {label} | {arms['baseline'][key]} | {arms['capture'][key]} |" for label, key in rows]
    for key in ("drafted", "accepted", "promoted"):
        lines.append(f"| {key} per session | {arms['baseline']['per-session'][key]} | "
                     f"{arms['capture']['per-session'][key]} |")
    lines.append(f"| lesson-test pass rate | {arms['baseline']['lesson-tests']['pass-rate']} | "
                 f"{arms['capture']['lesson-tests']['pass-rate']} |")
    lines += [
        "",
        f"Capture-arm proposals by trigger: `{json.dumps(arms['capture']['by-trigger'], sort_keys=True)}`",
        f"Accepted per session, capture minus baseline: {report['accepted-per-session-difference']}",
        f"Unattributed proposals (drafted outside a recorded session): {len(report['unattributed'])}",
        "",
        f"Decision rule: {report['decision-rule']}.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--hook", action="store_true", help="handle one harness hook event from stdin")
    action.add_argument("--report", type=pathlib.Path, metavar="CONSUMER_ROOT", help="print the capture A/B")
    parser.add_argument("--harness", choices=HARNESSES, help="the harness sending the event (--hook)")
    parser.add_argument("--format", choices=("json", "markdown"), default="json", help="--report output")
    args = parser.parse_args(argv)
    if args.hook:
        if not args.harness:
            parser.error("--hook needs --harness")
        output = run_hook(args.harness, sys.stdin.read())
        if output:
            print(output)
        return 0
    report = build_report(args.report)
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, indent=2, sort_keys=True),
          end="" if args.format == "markdown" else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
