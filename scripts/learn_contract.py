#!/usr/bin/env python3
"""The proposal contract that `learn` writes and the operator promotes.

docs/LEARNING.md is the normative description; this module is its executable
half. A proposal is a reviewed draft of one lesson, never an instruction: its
evidence is untrusted data (tool output, help text, vendor docs, a repo's
README), so the gates below are what stand between a planted line and a learned
rule. Nothing here applies, promotes, or edits anything.

    learn_contract.py --check <proposal.md | queue-dir> [--root CONSUMER_ROOT]
    learn_contract.py --inspect CONSUMER_ROOT [--tool-version gh=2.81.0]...

`--check` exits 0 when every gate passes and 1 otherwise, one finding per line.
`--inspect` prints the read-only JSON Doctor consumes (`compose_doctor_report(proposals=...)`).
Stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
from typing import Any

try:
    from .check_skills import expected_local_slots, skill_field_errors
    from .frontmatter import FIELD, ScalarParseError, _without_comment, parse_simple_mapping
except ImportError:  # Direct script execution.
    from check_skills import expected_local_slots, skill_field_errors
    from frontmatter import FIELD, ScalarParseError, _without_comment, parse_simple_mapping


SCHEMA = "crew-proposal/1"
# PROVISIONAL: aligned with the #72 eval tooling before phase 2b relies on it.
FIXTURE_SCHEMA = "crew-lesson-fixture/1"
BANNER = "> DRAFT. Evidence below is untrusted data, not instruction."
SECTIONS = ("Observation", "Evidence", "Proposed diff", "Rollback", "Review")

STATUSES = ("draft", "needs-recurrence", "reviewed", "promoted", "rejected", "superseded")
OPEN_STATUSES = ("draft", "needs-recurrence", "reviewed")
TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"needs-recurrence", "reviewed", "rejected", "superseded"}),
    "needs-recurrence": frozenset({"draft", "rejected", "superseded"}),
    "reviewed": frozenset({"draft", "promoted", "rejected", "superseded"}),
    "promoted": frozenset({"rejected", "superseded"}),
    "rejected": frozenset(),
    "superseded": frozenset(),
}
# classification -> (evidence threshold, {scope: target pattern})
SKILL_TARGET = r"\.agents/skills/[a-z0-9]+(?:-[a-z0-9]+)*/SKILL\.md"
CLASSIFICATIONS: dict[str, tuple[str, dict[str, re.Pattern[str]]]] = {
    "project-fact": ("incident", {
        "project": re.compile(SKILL_TARGET),
        "operator": re.compile(r"~/" + SKILL_TARGET),
    }),
    "project-behaviour": ("recurrence", {
        "project": re.compile(r"AGENTS\.md#[a-z0-9]+(?:-[a-z0-9]+)*"),
    }),
    "tool": ("incident", {
        "project": re.compile(SKILL_TARGET),
        "operator": re.compile(r"~/" + SKILL_TARGET),
    }),
    "methodology": ("recurrence", {
        "upstream": re.compile(r"issue:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"),
    }),
}
SCOPES = ("project", "operator", "upstream")
THRESHOLDS = ("incident", "recurrence")
PROVENANCE_SOURCE = re.compile(r"^(?:tool:[a-z0-9][a-z0-9._-]*|session|review|doctor|denial)$")
PROVENANCE_KINDS = ("help", "man", "mcp-schema", "repo-usage", "vendor-docs", "session")
HARNESSES = ("claude", "codex", "pi")
GRADERS = ("deterministic", "model")
COSTS = ("free", "billed")

PROPOSAL_ID = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$")
FILED_ISSUE = re.compile(r"^issue:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#[1-9]\d*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
REQUIRED_FIELDS = (
    "schema", "id", "status", "observation", "classification", "target", "target-sha256",
    "scope", "evidence-threshold", "occurrences", "provenance-source", "provenance-kind",
    "provenance-date", "provenance-tool-version", "provenance-harness", "provenance-crew",
    "promoted-in",
)
OPTIONAL_FIELDS = ("fixture",)

QUEUE_DECLARATION = re.compile(r"`proposal-queue:[ \t]*([^`\n]*?)[ \t]*`")
LEARNED_MARKER = re.compile(r"<!--[ \t]*crew:learned\b(.*?)-->", re.DOTALL)
MARKER_TOOL = re.compile(r"^([a-z0-9][a-z0-9._-]*)@(\S+)$")
FENCE = re.compile(r"^(```+|~~~+)[ \t]*([A-Za-z0-9_-]*)[^\n]*$")

# The verbatim-promotion gate: an added line that copies this many characters
# of an evidence excerpt is evidence being promoted to instruction.
VERBATIM_WINDOW = 40
ABSOLUTE_PATH = re.compile(r"(?<![\w:/.~-])(?:/(?:[\w.-]+/)+[\w.-]*|[A-Za-z]:\\[^\s`'\"]+)")
IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
URL_HOST = re.compile(r"\b[a-z][a-z0-9+.-]*://([^/\s`'\")>]+)", re.IGNORECASE)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
INTERNAL_HOST = re.compile(
    r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:internal|local|lan|corp|home|intranet|localdomain)\b",
    re.IGNORECASE,
)
DEEP_HOST = re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+){2,}\.[a-z]{2,}\b", re.IGNORECASE)
GIT_REMOTE = re.compile(r"^\s*url\s*=\s*(\S+)\s*$", re.MULTILINE)
REMOTE_SLUG = re.compile(r"[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")


def finding(gate: str, message: str) -> dict[str, str]:
    return {"gate": gate, "message": message}


# ---------------------------------------------------------------- queue location


def queue_location(agents_md: str) -> str | None:
    """The queue the project's AGENTS.md declares, or None (learn is report-only)."""
    values = list(dict.fromkeys(match.group(1) for match in QUEUE_DECLARATION.finditer(agents_md)))
    if not values:
        return None
    if len(values) > 1:
        raise ValueError(f"AGENTS.md declares conflicting proposal queues: {', '.join(values)}")
    return values[0]


def queue_location_errors(location: str) -> list[str]:
    """Why a declared queue location is unusable; empty when it is fine."""
    errors: list[str] = []
    path = pathlib.PurePosixPath(location.replace("\\", "/"))
    if not location.strip():
        return ["proposal-queue is empty; delete the line to keep learn report-only"]
    if path.is_absolute() or location.startswith("~") or re.match(r"^[A-Za-z]:", location):
        errors.append(f"proposal-queue {location!r} must be relative to the project root")
    if ".." in path.parts:
        errors.append(f"proposal-queue {location!r} escapes the project root")
    if any(part.lower() == "skills" for part in path.parts):
        errors.append(
            f"proposal-queue {location!r} is under a skills directory: harnesses load what sits "
            "there as instructions, and a proposal is unreviewed data"
        )
    if path.name.upper() == "SKILL.MD":
        errors.append(f"proposal-queue {location!r} names a SKILL.md")
    return errors


def find_project_root(start: pathlib.Path) -> pathlib.Path | None:
    """Nearest ancestor holding AGENTS.md; the project the queue belongs to."""
    start = pathlib.Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / "AGENTS.md").is_file():
            return candidate
    return None


# ------------------------------------------------------------------ parsing


def _split(text: str) -> tuple[list[str], list[str]] | None:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None
    return lines[1:end], lines[end + 1:]


def parse_fields(block: list[str]) -> dict[str, str]:
    """Flat frontmatter as strings: dates, versions and counts stay as written."""
    parsed = parse_simple_mapping("\n".join(block))
    fields: dict[str, str] = {}
    for line in block:
        match = FIELD.fullmatch(line)
        if not match:
            continue
        key, raw = match.groups()
        value = parsed.get(key)
        if isinstance(value, (list, dict)):
            raise ScalarParseError(f"{key} must be a flat scalar, not a collection")
        if isinstance(value, str):
            fields[key] = value
        else:
            fields[key] = _without_comment(raw.strip())
    return fields


def sections(body: list[str]) -> dict[str, list[str]]:
    """`## Heading` -> its lines, ignoring headings inside fenced blocks."""
    result: dict[str, list[str]] = {}
    current: str | None = None
    fence: str | None = None
    for line in body:
        match = FENCE.match(line)
        if match:
            if fence is None:
                fence = match.group(1)
            elif line.strip().startswith(fence) and not line.strip()[len(fence):].strip():
                fence = None
        if fence is None and line.startswith("## "):
            current = line[3:].strip()
            result.setdefault(current, [])
            continue
        if current is not None:
            result[current].append(line)
    return result


def fenced_blocks(lines: list[str]) -> list[tuple[str, list[str]]]:
    """(info tag, content lines) for each fenced block in `lines`."""
    blocks: list[tuple[str, list[str]]] = []
    fence: str | None = None
    tag = ""
    content: list[str] = []
    for line in lines:
        if fence is None:
            match = FENCE.match(line)
            if match:
                fence, tag, content = match.group(1), match.group(2), []
            continue
        stripped = line.strip()
        if stripped.startswith(fence) and not stripped[len(fence):].strip():
            blocks.append((tag, content))
            fence = None
            continue
        content.append(line)
    return blocks


def evidence_blocks(lines: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    """Parse ```evidence blocks: `source:` and `command:` headers, a blank line, the excerpt."""
    parsed: list[dict[str, str]] = []
    errors: list[str] = []
    for index, (tag, content) in enumerate(
        [block for block in fenced_blocks(lines) if block[0] == "evidence"], start=1
    ):
        headers: dict[str, str] = {}
        cursor = 0
        while cursor < len(content) and content[cursor].strip():
            key, _, value = content[cursor].partition(":")
            headers[key.strip().lower()] = value.strip()
            cursor += 1
        excerpt = "\n".join(content[cursor:]).strip("\n")
        for key in ("source", "command"):
            if not headers.get(key):
                errors.append(f"evidence block {index} has no `{key}:` header")
        if not excerpt.strip():
            errors.append(f"evidence block {index} has no excerpt after its headers")
        parsed.append({"source": headers.get("source", ""), "command": headers.get("command", ""),
                       "excerpt": excerpt})
    return parsed, errors


def parse_diff(lines: list[str]) -> dict[str, Any]:
    old = new = None
    files = 0
    added: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if line.startswith("--- "):
            old = line[4:].strip()
        elif line.startswith("+++ "):
            new = line[4:].strip()
            files += 1
        elif line.startswith("+"):
            added.append((number, line[1:]))
    return {"old": old, "new": new, "files": files, "added": added,
            "hunks": sum(1 for line in lines if line.startswith("@@"))}


def learned_markers(text: str) -> tuple[list[dict[str, str]], list[str]]:
    """Every `<!-- crew:learned proposal=<id> [tool=<x>@<v>] date=<d> -->` in a file."""
    markers: list[dict[str, str]] = []
    errors: list[str] = []
    for match in LEARNED_MARKER.finditer(text):
        values: dict[str, str] = {}
        for token in match.group(1).split():
            key, sep, value = token.partition("=")
            if not sep:
                errors.append(f"learned marker token {token!r} is not key=value")
                continue
            values[key] = value
        unknown = set(values) - {"proposal", "tool", "date"}
        if unknown:
            errors.append(f"learned marker has unknown keys {sorted(unknown)}")
        if not PROPOSAL_ID.match(values.get("proposal", "")):
            errors.append(f"learned marker proposal={values.get('proposal', '')!r} is not a proposal id")
        if not DATE.match(values.get("date", "")):
            errors.append(f"learned marker date={values.get('date', '')!r} is not YYYY-MM-DD")
        marker = {"proposal": values.get("proposal", ""), "date": values.get("date", ""),
                  "tool": "", "tool_version": ""}
        if "tool" in values:
            tool = MARKER_TOOL.match(values["tool"])
            if not tool:
                errors.append(f"learned marker tool={values['tool']!r} is not <tool>@<version>")
            else:
                marker["tool"], marker["tool_version"] = tool.groups()
        markers.append(marker)
    return markers, errors


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def verbatim_copies(added: list[tuple[int, str]], excerpts: list[str]) -> list[tuple[int, int, str]]:
    """(added line, evidence block, copied text) where an added line repeats evidence."""
    windows: list[set[str]] = []
    for excerpt in excerpts:
        flat = _normalized(excerpt)
        windows.append({flat[i:i + VERBATIM_WINDOW] for i in range(len(flat) - VERBATIM_WINDOW + 1)})
    copies: list[tuple[int, int, str]] = []
    for number, line in added:
        flat = _normalized(line)
        for block, seen in enumerate(windows, start=1):
            hit = next(
                (flat[i:i + VERBATIM_WINDOW] for i in range(len(flat) - VERBATIM_WINDOW + 1)
                 if flat[i:i + VERBATIM_WINDOW] in seen),
                None,
            )
            if hit:
                copies.append((number, block, hit))
                break
    return copies


def git_remote_slugs(root: pathlib.Path) -> list[str]:
    """owner/repo for every remote in `.git/config`; reads the file, runs no git."""
    git = pathlib.Path(root) / ".git"
    if git.is_file():  # A worktree: `gitdir: <path>`; its config lives in the common dir.
        pointer = git.read_text(encoding="utf-8").partition("gitdir:")[2].strip()
        gitdir = (git.parent / pointer).resolve()
        common = gitdir / "commondir"
        git = (gitdir / common.read_text(encoding="utf-8").strip()).resolve() if common.is_file() else gitdir
    config = git / "config"
    if not config.is_file():
        return []
    slugs = []
    for url in GIT_REMOTE.findall(config.read_text(encoding="utf-8")):
        match = REMOTE_SLUG.search(url)
        if match:
            slugs.append(f"{match.group(1)}/{match.group(2)}")
    return list(dict.fromkeys(slugs))


def context_leaks(text: str, *, project_names: list[str], remote_slugs: list[str]) -> list[str]:
    """Project context a portable lesson must not carry upstream."""
    leaks: list[str] = []
    folded = text.casefold()
    for name in project_names:
        if name and re.search(rf"(?<![\w-]){re.escape(name.casefold())}(?![\w-])", folded):
            leaks.append(f"project name {name!r}")
    for slug in remote_slugs:
        if slug.casefold() in folded:
            leaks.append(f"git remote {slug!r}")
    for pattern, label in (
        (ABSOLUTE_PATH, "absolute path"),
        (IPV4, "IP address"),
        (EMAIL, "email address"),
        (INTERNAL_HOST, "hostname"),
        (DEEP_HOST, "hostname"),
    ):
        for match in pattern.finditer(text):
            leaks.append(f"{label} {match.group(0)!r}")
    for match in URL_HOST.finditer(text):
        leaks.append(f"hostname {match.group(1)!r}")
    return list(dict.fromkeys(leaks))


# ------------------------------------------------------------------- fixture


def check_fixture(path: pathlib.Path, proposal_id: str) -> list[dict[str, str]]:
    """Validate a PROVISIONAL crew-lesson-fixture/1 file."""
    gate = "fixture"
    try:
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return [finding(gate, f"fixture {path.name} is unreadable JSON: {error}")]
    if not isinstance(data, dict):
        return [finding(gate, f"fixture {path.name} must be a JSON object")]
    problems: list[str] = []
    if data.get("schema") != FIXTURE_SCHEMA:
        problems.append(f"schema must be {FIXTURE_SCHEMA!r}")
    if data.get("proposal") != proposal_id:
        problems.append(f"proposal must be {proposal_id!r}, got {data.get('proposal')!r}")
    harness = data.get("harness")
    if not (harness == "any" or isinstance(harness, list) and harness and set(harness) <= set(HARNESSES)):
        problems.append(f"harness must be \"any\" or a non-empty list of {list(HARNESSES)}")
    files = (data.get("setup") or {}).get("files") if isinstance(data.get("setup"), dict) else None
    if not isinstance(files, dict) or not all(isinstance(v, str) for v in files.values()):
        problems.append("setup.files must map relative paths to file contents")
    else:
        for name in files:
            pure = pathlib.PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or not name:
                problems.append(f"setup.files path {name!r} must be relative and stay inside the scenario")
    if not isinstance(data.get("prompt"), str) or not data["prompt"].strip():
        problems.append("prompt must be a non-empty string")
    before = data.get("before")
    if not (isinstance(before, dict) and isinstance(before.get("excerpt"), str) and before["excerpt"].strip()):
        problems.append("before.excerpt must record the original failure")
    expect = data.get("expect")
    if not isinstance(expect, dict):
        problems.append("expect must be an object")
    else:
        loads = expect.get("loads_skill")
        if loads is not None and not (isinstance(loads, str) and loads):
            problems.append("expect.loads_skill must be a skill name or null")
        for key in ("must_include", "must_not_include"):
            value = expect.get(key, [])
            if not (isinstance(value, list) and all(isinstance(item, str) and item for item in value)):
                problems.append(f"expect.{key} must be a list of strings")
        if not loads and not expect.get("must_include") and not expect.get("must_not_include"):
            problems.append("expect asserts nothing: set loads_skill, must_include or must_not_include")
    if data.get("grader") not in GRADERS:
        problems.append(f"grader must be one of {list(GRADERS)}")
    if data.get("cost") not in COSTS:
        problems.append(f"cost must be one of {list(COSTS)}")
    elif data.get("grader") == "model" and data.get("cost") != "billed":
        problems.append("a model grader is a model call: cost must be billed")
    return [finding(gate, f"fixture {path.name}: {problem}") for problem in problems]


# ------------------------------------------------------------------ proposal


def check_transition(old: str, new: str) -> bool:
    """Whether a status change is one docs/LEARNING.md allows."""
    return new in TRANSITIONS.get(old, frozenset())


def queue_findings(queue: pathlib.Path, root: pathlib.Path | None) -> list[dict[str, str]]:
    """The queue gate: judged relative to the project root when there is one."""
    queue = pathlib.Path(queue).resolve()
    if root and queue.is_relative_to(pathlib.Path(root).resolve()):
        location = queue.relative_to(pathlib.Path(root).resolve()).as_posix()
        return [finding("queue", error) for error in queue_location_errors(location)]
    if any(part.lower() == "skills" for part in queue.parts):
        return [finding("queue", f"{queue} is under a skills directory: harnesses load what sits there")]
    return []


def check_proposal(
    path: pathlib.Path, *, root: pathlib.Path | None = None, check_location: bool = True
) -> list[dict[str, str]]:
    """Every gate a proposal file fails; empty when it passes."""
    path = pathlib.Path(path)
    root = pathlib.Path(root) if root else find_project_root(path.parent)
    if path.name.upper() == "SKILL.MD":
        return [finding("queue", "a proposal is never named SKILL.md: harnesses would load it as a skill")]
    found = queue_findings(path.parent, root) if check_location else []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return found + [finding("fields", f"unreadable: {error}")]
    split = _split(text)
    if split is None:
        return found + [finding("fields", "missing or unterminated leading YAML frontmatter")]
    block, body = split
    try:
        fields = parse_fields(block)
    except ScalarParseError as error:
        return found + [finding("fields", f"invalid frontmatter: {error}")]

    found.extend(_field_findings(path, fields))
    structure = sections(body)
    found.extend(_structure_findings(body, structure))
    evidence, evidence_errors = evidence_blocks(structure.get("Evidence", []))
    found.extend(finding("structure", error) for error in evidence_errors)
    if "Evidence" in structure and not evidence:
        found.append(finding("structure", "## Evidence has no ```evidence block"))

    classification = fields.get("classification", "")
    proposed = structure.get("Proposed diff", [])
    blocks = fenced_blocks(proposed)
    promoted_lines: list[tuple[int, str]] = []
    if classification == "methodology":
        issues = [content for tag, content in blocks if tag == "issue"]
        if len(issues) != 1 or not "\n".join(issues[0]).strip():
            found.append(finding("structure", "a methodology proposal carries one ```issue block, not a diff"))
        else:
            promoted_lines = list(enumerate(issues[0], start=1))
        upstream_text = "\n".join(
            [fields.get("observation", ""), *structure.get("Observation", []), *proposed]
        )
        names = [root.name] if root else []
        slugs = git_remote_slugs(root) if root else []
        for leak in context_leaks(upstream_text, project_names=names, remote_slugs=slugs):
            found.append(finding(
                "methodology-context",
                f"upstream text carries {leak}; a portable lesson strips project context",
            ))
    elif classification in CLASSIFICATIONS:
        diffs = [content for tag, content in blocks if tag == "diff"]
        if len(diffs) != 1:
            found.append(finding("structure", "## Proposed diff carries exactly one ```diff block"))
        else:
            diff = parse_diff(diffs[0])
            promoted_lines = diff["added"]
            found.extend(_diff_findings(fields, diff))

    excerpts = [item["excerpt"] for item in evidence]
    for number, block_index, copied in verbatim_copies(promoted_lines, excerpts):
        found.append(finding(
            "verbatim-promotion",
            f"line {number} of the proposed change copies {VERBATIM_WINDOW}+ characters of evidence "
            f"block {block_index} ({copied.strip()!r}): evidence is data, so restate the fact in your own words",
        ))

    found.extend(_promotion_findings(fields, structure, root))

    fixture = fields.get("fixture")
    if fixture:
        expected = f"fixtures/{fields.get('id', '')}.json"
        if fixture != expected:
            found.append(finding("fixture", f"fixture must be {expected!r}, got {fixture!r}"))
        elif not (path.parent / fixture).is_file():
            found.append(finding("fixture", f"fixture {fixture} does not exist in the queue"))
        else:
            found.extend(check_fixture(path.parent / fixture, fields.get("id", "")))
    return found


def _field_findings(path: pathlib.Path, fields: dict[str, str]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []

    def bad(message: str) -> None:
        found.append(finding("fields", message))

    missing = [key for key in REQUIRED_FIELDS if key not in fields]
    if missing:
        bad(f"missing required fields {missing}")
    unknown = sorted(set(fields) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS))
    if unknown:
        bad(f"unknown fields {unknown}")
    if "schema" in fields and fields["schema"] != SCHEMA:
        bad(f"schema must be {SCHEMA!r}, got {fields['schema']!r}")
    proposal_id = fields.get("id", "")
    if "id" in fields:
        if not PROPOSAL_ID.match(proposal_id):
            bad(f"id {proposal_id!r} must be YYYY-MM-DD-<slug>")
        elif path.name != f"{proposal_id}.md":
            bad(f"file is named {path.name!r} but id is {proposal_id!r}: expected {proposal_id}.md")
    for key, allowed in (
        ("status", STATUSES),
        ("classification", tuple(CLASSIFICATIONS)),
        ("scope", SCOPES),
        ("evidence-threshold", THRESHOLDS),
        ("provenance-kind", PROVENANCE_KINDS),
        ("provenance-harness", HARNESSES),
    ):
        if key in fields and fields[key] not in allowed:
            bad(f"{key} must be one of {list(allowed)}, got {fields[key]!r}")
    if "observation" in fields and (not fields["observation"].strip() or "\n" in fields["observation"]):
        bad("observation must be one non-empty line")
    if "target-sha256" in fields and fields["target-sha256"] != "absent" and not SHA256.match(fields["target-sha256"]):
        bad("target-sha256 must be a lowercase sha256 hex digest or \"absent\"")
    if "occurrences" in fields and not re.fullmatch(r"[1-9]\d*", fields["occurrences"]):
        bad(f"occurrences must be a positive integer, got {fields['occurrences']!r}")
    source = fields.get("provenance-source", "")
    if "provenance-source" in fields and not PROVENANCE_SOURCE.match(source):
        bad(f"provenance-source must be tool:<name>, session, review, doctor or denial, got {source!r}")
    if source.startswith("tool:") and not fields.get("provenance-tool-version"):
        bad("a tool-sourced proposal records provenance-tool-version, so Doctor can flag staleness")
    if "provenance-date" in fields and not DATE.match(fields["provenance-date"]):
        bad(f"provenance-date must be YYYY-MM-DD, got {fields['provenance-date']!r}")
    if "provenance-crew" in fields and not SEMVER.match(fields["provenance-crew"]):
        bad(f"provenance-crew must be the Crew version X.Y.Z, got {fields['provenance-crew']!r}")

    classification = fields.get("classification")
    if classification in CLASSIFICATIONS:
        threshold, targets = CLASSIFICATIONS[classification]
        if fields.get("evidence-threshold", threshold) != threshold:
            found.append(finding(
                "classification",
                f"a {classification} lesson needs evidence-threshold {threshold}, "
                f"got {fields.get('evidence-threshold')!r}",
            ))
        scope = fields.get("scope")
        if scope in SCOPES and scope not in targets:
            found.append(finding(
                "classification",
                f"a {classification} lesson has scope {' or '.join(targets)}, got {scope!r}",
            ))
        elif scope in targets and "target" in fields and not targets[scope].fullmatch(fields["target"]):
            found.append(finding(
                "classification",
                f"a {scope}-scope {classification} lesson targets {targets[scope].pattern!r}, "
                f"got {fields['target']!r}",
            ))
        if threshold == "recurrence" and fields.get("occurrences", "").isdigit():
            if int(fields["occurrences"]) < 2 and fields.get("status") in {"draft", "reviewed", "promoted"}:
                found.append(finding(
                    "classification",
                    f"a {classification} lesson needs recurrence: with occurrences 1 its status "
                    "is needs-recurrence until a second incident is recorded",
                ))
        if threshold == "incident" and fields.get("status") == "needs-recurrence":
            found.append(finding(
                "classification", f"a {classification} lesson needs one incident, not needs-recurrence"
            ))
    if classification == "methodology" and fields.get("target-sha256", "absent") != "absent":
        bad("a methodology proposal targets an issue: target-sha256 is \"absent\"")

    status = fields.get("status")
    promoted_in = fields.get("promoted-in", "")
    if status == "promoted" and classification == "methodology":
        if not FILED_ISSUE.match(promoted_in):
            bad("a promoted methodology proposal records promoted-in: issue:<owner>/<repo>#<number>")
    elif status == "promoted" and not COMMIT.match(promoted_in):
        bad("a promoted proposal records promoted-in: the commit to roll back")
    if status != "promoted" and promoted_in and status not in {"rejected", "superseded"}:
        bad(f"promoted-in is set but status is {status!r}")
    return found


def _structure_findings(body: list[str], structure: dict[str, list[str]]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    first = next((line for line in body if line.strip()), "")
    if first.strip() != BANNER:
        found.append(finding("structure", f"the body must open with {BANNER!r}"))
    present = [name for name in structure if name in SECTIONS]
    for name in SECTIONS:
        if name not in structure:
            found.append(finding("structure", f"missing section ## {name}"))
    if [name for name in SECTIONS if name in present] != present:
        found.append(finding("structure", f"sections must appear in order: {', '.join(SECTIONS)}"))
    for name in ("Observation", "Rollback"):
        if name in structure and not "\n".join(structure[name]).strip():
            found.append(finding("structure", f"## {name} is empty"))
    return found


def _diff_findings(fields: dict[str, str], diff: dict[str, Any]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    target = fields.get("target", "")
    target_file = target.split("#", 1)[0]
    new_file = fields.get("target-sha256") == "absent"
    if diff["files"] != 1 or not diff["hunks"]:
        found.append(finding("structure", "the diff changes exactly one file with at least one hunk"))
        return found
    if diff["new"] not in {f"b/{target_file}", target_file}:
        found.append(finding("structure", f"the diff writes {diff['new']!r}, but target is {target_file!r}"))
    if new_file != (diff["old"] == "/dev/null"):
        found.append(finding(
            "structure",
            "target-sha256 \"absent\" means a new file, so the diff starts from /dev/null (and only then)",
        ))
    if not target_file.endswith("/SKILL.md"):
        return found

    added_text = "\n".join(line for _, line in diff["added"])
    markers, marker_errors = learned_markers(added_text)
    found.extend(finding("learned-marker", error) for error in marker_errors)
    own = [marker for marker in markers if marker["proposal"] == fields.get("id")]
    if not own:
        found.append(finding(
            "learned-marker",
            f"the diff must add <!-- crew:learned proposal={fields.get('id', '<id>')} ... --> "
            "so check_skills --local and Doctor can find the learned skill",
        ))
    source = fields.get("provenance-source", "")
    if own and source.startswith("tool:"):
        expected = (source[5:], fields.get("provenance-tool-version", ""))
        if (own[0]["tool"], own[0]["tool_version"]) != expected:
            found.append(finding(
                "learned-marker",
                f"the marker must carry tool={expected[0]}@{expected[1]} to match provenance",
            ))
    if new_file:
        lines = [line for _, line in diff["added"]]
        split = _split("\n".join(lines))
        rel = target_file
        if split is None:
            found.append(finding("new-skill-schema", f"{rel}: the new skill has no leading frontmatter"))
        else:
            try:
                fm = parse_simple_mapping("\n".join(split[0]))
            except ScalarParseError as error:
                found.append(finding("new-skill-schema", f"{rel}: invalid frontmatter: {error}"))
            else:
                errors, _ = skill_field_errors(rel, fm, pathlib.PurePosixPath(target_file).parent.name,
                                               expected_local_slots())
                if "provides" in fm:
                    errors.append(f"{rel}: provides is pack-only")
                found.extend(finding("new-skill-schema", error) for error in errors)
    return found


def _promotion_findings(
    fields: dict[str, str], structure: dict[str, list[str]], root: pathlib.Path | None
) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    status = fields.get("status")
    review = "\n".join(structure.get("Review", []))
    if status in {"reviewed", "promoted"} and not re.search(r"^verdict:[ \t]*accept\b", review, re.MULTILINE):
        found.append(finding("review", f"a {status} proposal records `verdict: accept` under ## Review"))
    target = fields.get("target", "")
    if status != "promoted" or not target.endswith("/SKILL.md") or target.startswith("~/"):
        return found
    if root is None:
        found.append(finding("learned-marker", "cannot find the project root (no AGENTS.md) to verify the promoted skill"))
        return found
    skill = root / target
    try:
        markers, _ = learned_markers(skill.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        found.append(finding("learned-marker", f"promoted target {target} is not readable in {root}"))
        return found
    if not any(marker["proposal"] == fields.get("id") for marker in markers):
        found.append(finding(
            "learned-marker",
            f"promoted skill {target} carries no crew:learned marker for {fields.get('id')}",
        ))
    return found


def read_proposal(path: pathlib.Path) -> dict[str, str] | None:
    split = _split(pathlib.Path(path).read_text(encoding="utf-8"))
    if split is None:
        return None
    try:
        return parse_fields(split[0])
    except ScalarParseError:
        return None


def check_queue(queue: pathlib.Path, *, root: pathlib.Path | None = None) -> dict[str, list[dict[str, str]]]:
    """path -> findings for every proposal in a queue, plus queue-level findings under ''."""
    queue = pathlib.Path(queue)
    root = pathlib.Path(root) if root else find_project_root(queue)
    results: dict[str, list[dict[str, str]]] = {"": queue_findings(queue, root)}
    for skill in sorted(queue.rglob("SKILL.md")):
        results[""].append(finding("queue", f"{skill.relative_to(queue)}: a queue holds no SKILL.md"))
    ids: dict[str, str] = {}
    for path in sorted(queue.glob("*.md")):
        if path.name.upper() in {"README.MD", "SKILL.MD"}:
            continue
        found = check_proposal(path, root=root, check_location=False)
        fields = read_proposal(path) or {}
        if fields.get("id") in ids:
            found.append(finding("fields", f"duplicate id {fields['id']!r} (also {ids[fields['id']]})"))
        elif fields.get("id"):
            ids[fields["id"]] = path.name
        results[str(path)] = found
    return results


# ------------------------------------------------------------------- Doctor


def _sha256(path: pathlib.Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def inspect_proposals(
    consumer_root: pathlib.Path, *, tool_versions: dict[str, str] | None = None
) -> dict[str, Any]:
    """Read-only evidence for Doctor's proposals.* and learned.* rows.

    `tool_versions` are the agent's own observations (e.g. `gh --version`);
    without them, version staleness stays untested rather than guessed.
    """
    root = pathlib.Path(consumer_root)
    agents_md = root / "AGENTS.md"
    result: dict[str, Any] = {
        "agents_md": str(agents_md), "declared": False, "queue": None, "queue_errors": [],
        "proposals": [], "learned_skills": [], "tool_versions": dict(tool_versions or {}),
    }
    try:
        text = agents_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    try:
        location = queue_location(text)
    except ValueError as error:
        result["declared"] = True
        result["queue_errors"].append(str(error))
        location = None
    promoted_in: dict[str, str] = {}
    if location is not None:
        result["declared"] = True
        queue = root / location
        result["queue"] = str(queue)
        result["queue_errors"].extend(queue_location_errors(location))
        if queue.is_dir() and not result["queue_errors"]:
            checked = check_queue(queue, root=root)
            result["queue_errors"].extend(item["message"] for item in checked.pop(""))
            for path, found in checked.items():
                fields = read_proposal(pathlib.Path(path)) or {}
                entry = {
                    "path": path, "id": fields.get("id", ""), "status": fields.get("status", ""),
                    "target": fields.get("target", ""), "errors": [f"[{f['gate']}] {f['message']}" for f in found],
                    "stale": [], "untested": [],
                }
                if fields.get("status") == "promoted":
                    promoted_in[fields.get("id", "")] = fields.get("promoted-in", "")
                if fields.get("status") in OPEN_STATUSES:
                    target = fields.get("target", "").split("#", 1)[0]
                    expected = fields.get("target-sha256", "")
                    if target and not target.startswith(("issue:", "~/")):
                        actual = _sha256(root / target) or "absent"
                        if expected and actual != expected:
                            entry["stale"].append(f"{target} changed since the proposal was drafted")
                    source = fields.get("provenance-source", "")
                    if source.startswith("tool:"):
                        tool = source[5:]
                        current = result["tool_versions"].get(tool)
                        recorded = fields.get("provenance-tool-version", "")
                        if current is None:
                            entry["untested"].append(f"current {tool} version not supplied")
                        elif current != recorded:
                            entry["stale"].append(f"{tool} is {current}; the evidence is from {recorded}")
                result["proposals"].append(entry)
    seen: set[pathlib.Path] = set()
    for rel_dir in (".agents/skills", ".claude/skills"):
        for skill in sorted((root / rel_dir).glob("*/SKILL.md")):
            if skill.resolve() in seen:
                continue
            seen.add(skill.resolve())
            try:
                markers, _ = learned_markers(skill.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
            for marker in markers:
                current = result["tool_versions"].get(marker["tool"]) if marker["tool"] else None
                result["learned_skills"].append({
                    "path": str(skill), "proposal": marker["proposal"], "tool": marker["tool"],
                    "version": marker["tool_version"], "current_version": current,
                    "promoted_in": promoted_in.get(marker["proposal"], ""),
                })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", type=pathlib.Path, metavar="PATH", help="a proposal file or a queue directory")
    mode.add_argument("--inspect", type=pathlib.Path, metavar="CONSUMER_ROOT", help="print Doctor's evidence as JSON")
    parser.add_argument("--root", type=pathlib.Path, help="consumer root (default: nearest ancestor with AGENTS.md)")
    parser.add_argument("--tool-version", action="append", default=[], metavar="TOOL=VERSION",
                        help="an observed tool version for --inspect staleness")
    args = parser.parse_args(argv)
    if args.inspect:
        versions = dict(item.split("=", 1) for item in args.tool_version if "=" in item)
        print(json.dumps(inspect_proposals(args.inspect, tool_versions=versions), indent=2, sort_keys=True))
        return 0
    target: pathlib.Path = args.check
    if target.is_dir():
        results = check_queue(target, root=args.root)
    elif target.is_file():
        results = {str(target): check_proposal(target, root=args.root)}
    else:
        print(f"{target}: no such proposal or queue", file=sys.stderr)
        return 2
    failures = 0
    for path, found in results.items():
        for item in found:
            failures += 1
            print(f"{path or target}: [{item['gate']}] {item['message']}")
    checked = len([path for path in results if path])
    if failures:
        print(f"\n{failures} finding(s) in {checked} proposal(s)")
        return 1
    print(f"{checked} proposal(s) pass every gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
