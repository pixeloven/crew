#!/usr/bin/env python3
"""Deterministic lifecycle boundary shared by the Onboarding skill and tests."""

import argparse
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import Any

try:
    from .crew_doctor import MOVED_SKILL_REFERENCE, MOVED_SKILLS, PLUGIN_NAME, PROFILE_TAXONOMY
    from .learn_contract import queue_location, queue_location_errors
except ImportError:  # Direct script execution.
    from crew_doctor import MOVED_SKILL_REFERENCE, MOVED_SKILLS, PLUGIN_NAME, PROFILE_TAXONOMY
    from learn_contract import queue_location, queue_location_errors
try:
    from .check_skills import PACK_SLOT_STUBS, stub_sections
except ImportError:  # Direct script execution.
    from check_skills import PACK_SLOT_STUBS, stub_sections
try:
    from .crew_inventory import (
        CAPABILITIES_HEADING,
        FILL,
        capability_map_rows,
        parse_capability_map,
        render_capability_map,
    )
except ImportError:  # Direct script execution.
    from crew_inventory import (
        CAPABILITIES_HEADING,
        FILL,
        capability_map_rows,
        parse_capability_map,
        render_capability_map,
    )


class ApplyAuthorizationRequired(ValueError):
    """Raised when mutation is requested without a distinct authorization."""


@dataclass
class HostApplyAuthorizationSignal:
    """One-use host decision for one currently executing onboarding invocation."""

    invocation_id: str
    host_verified: bool
    scope: str = "current-invocation"
    persisted: bool = False
    _consumed: bool = False

    def consume(self, invocation_id: str) -> None:
        """Consume a fresh host-verified signal without authenticating or persisting it."""
        if (
            not self.host_verified
            or self.scope != "current-invocation"
            or self.persisted
            or self._consumed
            or not invocation_id
            or self.invocation_id != invocation_id
        ):
            raise ApplyAuthorizationRequired(
                "apply requires a fresh, non-persisted authorization signal verified by the "
                "supervising host for this invocation"
            )
        self._consumed = True


@dataclass(frozen=True)
class OnboardingMode:
    mode: str
    writes_allowed: bool
    authorization_verified: bool
    stop_boundary: str
    preserve: tuple[str, ...]
    destructive_change_interface: str
    implementation_validation_owner: str
    may_declare_delivery_complete: bool
    required_spine_sections: tuple[str, ...]


PRESERVE = (
    "mature-entry-files",
    "safety-tripwires",
    "project-delivery-contracts",
    "runbook-pointers",
)

# Spine sections an onboarded AGENTS.md must carry even when it is mature and
# project-written. Doctor reports their absence as drift; apply inserts them.
REQUIRED_SPINE_SECTIONS = ("reporting-contract",)


def resolve_mode(
    *,
    explicit_audit: bool = False,
    explicit_apply: bool = False,
    invocation_id: str | None = None,
    authorization: HostApplyAuthorizationSignal | None = None,
) -> OnboardingMode:
    """Resolve plain onboarding to audit; trust only a current host decision."""
    if explicit_audit and explicit_apply:
        raise ValueError("audit and apply are mutually exclusive")
    if explicit_apply:
        if not isinstance(authorization, HostApplyAuthorizationSignal) or not invocation_id:
            raise ApplyAuthorizationRequired(
                "apply requires a fresh current-invocation authorization signal from the supervising host"
            )
        authorization.consume(invocation_id)

    applying = explicit_apply
    return OnboardingMode(
        mode="apply" if applying else "audit",
        writes_allowed=applying,
        authorization_verified=applying,
        stop_boundary="implementation handed to host workflow" if applying else "audit report delivered",
        preserve=PRESERVE,
        destructive_change_interface="host escalation/decision interface",
        implementation_validation_owner="host project workflow",
        may_declare_delivery_complete=False,
        required_spine_sections=REQUIRED_SPINE_SECTIONS,
    )


def consume_doctor_profile(profile: str) -> str:
    """Validate the typed Doctor → Onboarding handoff."""
    if profile not in PROFILE_TAXONOMY:
        raise ValueError(f"unknown Doctor profile {profile!r}; expected one of {PROFILE_TAXONOMY}")
    return profile


_REPORTING_HEADING = re.compile(r"^#{2,3}[ \t]+reporting contract\b.*$", re.IGNORECASE | re.MULTILINE)
_DECISION_LINE = re.compile(r"decisions?\s+needed", re.IGNORECASE)
_TRIPWIRES_HEADING = re.compile(r"^##[ \t]+tripwires\b", re.IGNORECASE | re.MULTILINE)


def _section_bounds(text: str) -> tuple[int, int] | None:
    match = _REPORTING_HEADING.search(text)
    if not match:
        return None
    level = len(match.group(0)) - len(match.group(0).lstrip("#"))
    following = re.compile(rf"^#{{1,{level}}}[ \t]", re.MULTILINE)
    end = following.search(text, match.end())
    return match.start(), end.start() if end else len(text)


def reporting_contract_section(text: str) -> str:
    """Return the reporting-contract section of an entry file, or ``""``."""
    bounds = _section_bounds(text)
    return text[bounds[0]:bounds[1]].rstrip() + "\n" if bounds else ""


def audit_reporting_contract(text: str | None) -> dict[str, Any]:
    """Read-only presence check Doctor and audit share; never edits anything."""
    recommendation = "run onboarding apply to merge the reporting contract from templates/AGENTS.md"
    if text is None:
        return {
            "check": "reporting-contract",
            "status": "MISSING",
            "fact": "no AGENTS.md, so no reporting contract",
            "recommendation": recommendation,
        }
    section = reporting_contract_section(text)
    if not section:
        return {
            "check": "reporting-contract",
            "status": "MISSING",
            "fact": "AGENTS.md has no reporting contract section",
            "recommendation": recommendation,
        }
    if not _DECISION_LINE.search(section):
        return {
            "check": "reporting-contract",
            "status": "DEGRADED",
            "fact": "reporting contract section does not require a leading decisions line",
            "recommendation": "restore the decisions-first rule from templates/AGENTS.md",
        }
    return {
        "check": "reporting-contract",
        "status": "OK",
        "fact": "reporting contract present with a decisions-first rule",
        "recommendation": "",
    }


def ensure_reporting_contract(text: str, template: str) -> str:
    """Merge the template's section into an entry file; never replaces a project's own."""
    if _section_bounds(text):
        return text
    section = reporting_contract_section(template)
    if not section:
        raise ValueError("template carries no reporting contract section")
    anchor = _TRIPWIRES_HEADING.search(text)
    if anchor:
        return text[:anchor.start()] + section + "\n" + text[anchor.start():]
    return text.rstrip("\n") + "\n\n" + section


def audit_moved_skill_references(text: str) -> list[dict[str, Any]]:
    """Propose a namespace update for each reference to a skill that left Crew.

    `crew:<skill>` becomes `<pack>:<skill>`; a bare name (pi's flat namespace)
    keeps its spelling and only needs the pack installed. Already-updated
    references are not proposals. Read-only.
    """
    proposals = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in MOVED_SKILL_REFERENCE.finditer(line):
            namespace, skill = match.group("namespace"), match.group("skill")
            pack = MOVED_SKILLS[skill]
            if namespace and namespace != PLUGIN_NAME:
                continue
            proposals.append(
                {
                    "line": number,
                    "skill": skill,
                    "pack": pack,
                    "from": match.group(0),
                    "to": f"{pack}:{skill}" if namespace else skill,
                }
            )
    return proposals


def rewrite_moved_skill_references(text: str) -> str:
    """Apply-mode rewrite of `crew:<skill>` to `<pack>:<skill>`; idempotent."""
    def replace(match: re.Match[str]) -> str:
        if match.group("namespace") != PLUGIN_NAME:
            return match.group(0)
        skill = match.group("skill")
        return f"{MOVED_SKILLS[skill]}:{skill}"

    return MOVED_SKILL_REFERENCE.sub(replace, text)


def merge_capability_map(slot_text: str, inventory: dict[str, Any], *, today: str | None = None) -> str:
    """Merge the inventory's capability map into an `agent-runtime` slot; idempotent.

    Only the text between the `crew:capability-map` markers changes. Operator-written
    Fallback cells survive, a vanished capability stays as `absent` and is listed
    for an authorized removal, and missing markers append a `## Capabilities`
    section. An unchanged map keeps its date, so re-running never churns.
    """
    recorded = parse_capability_map(slot_text)
    current = {row["capability"] for row in capability_map_rows(inventory)}
    fallbacks: dict[str, str] = {}
    retained: list[dict[str, str]] = []
    generated = today
    crew = None
    if recorded:
        for row in recorded["rows"]:
            if row["fallback"] and row["fallback"] != FILL:
                fallbacks[row["capability"]] = row["fallback"]
            if row["capability"] not in current:
                retained.append({**{key: row[key] for key in ("capability", "provider", "kind")}, "state": "absent"})
        if recorded["digest"] == inventory["map_digest"] and recorded["generated"]:
            generated, crew = recorded["generated"], recorded["crew"]
    block = render_capability_map(
        inventory, fallbacks=fallbacks, retained=retained, generated=generated, crew=crew
    )
    if recorded:
        start, stop = recorded["span"]
        return slot_text[:start] + block + slot_text[stop:]
    heading = CAPABILITIES_HEADING.search(slot_text)
    if heading:
        following = re.compile(r"^#{1,2}[ \t]", re.MULTILINE).search(slot_text, heading.end())
        cut = following.start() if following else len(slot_text)
        head = slot_text[:cut].rstrip("\n")
        tail = slot_text[cut:]
        return head + "\n\n" + block + "\n" + ("\n" + tail if tail else "")
    return slot_text.rstrip("\n") + "\n\n## Capabilities\n\n" + block + "\n"


def _skill_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "project"


def capability_map_proposal(
    inventory: dict[str, Any],
    contract: OnboardingMode,
    *,
    template_text: str,
    today: str | None = None,
) -> dict[str, Any]:
    """Audit reports the diff; apply also gets the text to write. Never writes.

    With no `agent-runtime` fill, the proposal creates `<project>-agent-runtime`
    from the stub. A pack-provided fill is a host decision: a new local fill
    would outrank the pack.
    """
    import difflib

    capability_map = inventory["capability_map"]
    project = pathlib.Path(inventory["project_root"])
    if capability_map["fill"] == "pack":
        return {
            "action": "decision-needed",
            "target": None,
            "diff": "",
            "text": None,
            "removals": [],
            "reason": (
                f"agent-runtime is filled by a pack ({capability_map['source']}); a local fill "
                "carrying the map would outrank it"
            ),
        }
    if capability_map["fill"] == "local":
        target = pathlib.Path(capability_map["source"])
        before = target.read_text(encoding="utf-8")
        action = "merge"
    else:
        name = f"{_skill_slug(project.name)}-agent-runtime"
        target = project / ".agents/skills" / name / "SKILL.md"
        before = ""
        action = "create"
    base = before or template_text.replace("<project>", _skill_slug(project.name)).replace(
        "<Project>", project.name
    )
    after = merge_capability_map(base, inventory, today=today)
    if after == before:
        action = "unchanged"
    diff = "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=str(target) if before else "/dev/null",
            tofile=str(target),
        )
    )
    recorded = parse_capability_map(after) or {"removals": []}
    return {
        "action": action,
        "target": str(target),
        "diff": diff,
        "text": after if contract.writes_allowed and action != "unchanged" else None,
        "removals": recorded["removals"],
        "reason": "",
    }


DEPTH_MODES = ("scaffold", "deepen")
# Filled by `capability_map_proposal`, which creates the fill from its stub.
CAPABILITY_MAP_SLOT = "agent-runtime"


def _section_split(sections: list[dict[str, Any]], depth: str) -> dict[str, Any]:
    """Unfilled sections by who answers them. Scaffold defers `crew:optional` ones."""
    discoverable: list[dict[str, Any]] = []
    human: list[str] = []
    deferred: list[str] = []
    for section in sections:
        if not section["unfilled"]:
            continue
        if section["optional"] and depth == "scaffold":
            deferred.append(section["heading"])
        elif section["discoverable"]:
            discoverable.append({
                "heading": section["heading"],
                "capability": section["discoverable"],
                "capabilities": list(section["capabilities"]),
            })
        else:
            human.append(section["heading"])
    return {"discoverable_sections": discoverable, "human_sections": human, "deferred_sections": deferred}


def pack_slot_proposals(
    inventory: dict[str, Any],
    contract: OnboardingMode,
    *,
    crew_root: pathlib.Path,
    depth: str = "scaffold",
) -> list[dict[str, Any]]:
    """Propose a local fill for each unfilled declared slot, from its owner's stub. Never writes.

    A pack's slot starts from that pack's `templates/local-skills/<slot>.md`; a
    Crew slot from Crew's. The fill is `<project>-<slot>` in `.agents/skills/`.
    Unfilled stub sections split into `discoverable_sections` (handed to learn)
    and `human_sections` (the interview); Scaffold puts `crew:optional` ones in
    `deferred_sections`. A local fill still carrying `▸ Fill` is `complete`d in
    place by the interview, so it gets no `text`. A slot a pack fills is not
    proposed: a local fill would outrank it, which is a host decision. Only
    apply carries `text`, and only for `create`.
    """
    import difflib

    if depth not in DEPTH_MODES:
        raise ValueError(f"unknown depth {depth!r}; expected one of {DEPTH_MODES}")
    project = pathlib.Path(inventory["project_root"])
    slug = _skill_slug(project.name)
    slots = inventory["slots"]
    pack_slots = slots.get("pack_slots", {})
    collisions = {collision["slot"]: collision for collision in slots.get("collisions", [])}
    pack_roots = {pack["name"]: pack["root"] for pack in inventory.get("packs", [])}
    proposals: list[dict[str, Any]] = []
    for slot, entry in sorted(slots["slots"].items()):
        owners = pack_slots.get(slot, [])
        proposal: dict[str, Any] = {
            "slot": slot,
            "pack": owners[0] if len(owners) == 1 else None,
            "stub": None,
            "target": None,
            "action": "",
            "depth": depth,
            "discoverable_sections": [],
            "human_sections": [],
            "deferred_sections": [],
            "diff": "",
            "text": None,
            "reason": "",
        }
        if entry["local"]:
            fill = entry["local"][0]
            if not fill.get("unfilled_sections"):
                continue
            sections, _ = stub_sections(pathlib.Path(fill["source"]).read_text(encoding="utf-8"))
            proposals.append(
                {**proposal, "target": fill["source"], "action": "complete", **_section_split(sections, depth)}
            )
            continue
        if entry["packs"] or slot == CAPABILITY_MAP_SLOT:
            continue
        if slot in collisions:
            named = ", ".join(f"`{name}`" for name in collisions[slot]["packs"])
            by = f"Crew and pack {named}" if collisions[slot]["crew"] else f"packs {named}"
            proposals.append({**proposal, "action": "decision-needed",
                              "reason": f"slot `{slot}` is declared by {by}; its owner is ambiguous"})
            continue
        root = pathlib.Path(pack_roots[owners[0]]) if owners else pathlib.Path(crew_root)
        stub = root / PACK_SLOT_STUBS / f"{slot}.md"
        target = project / ".agents/skills" / f"{slug}-{slot}" / "SKILL.md"
        proposal["target"] = str(target)
        if not stub.is_file():
            owner = f"pack `{owners[0]}`" if owners else "Crew"
            proposals.append({**proposal, "action": "decision-needed",
                              "reason": f"{owner} ships no stub for slot `{slot}` at {stub}"})
            continue
        text = stub.read_text(encoding="utf-8").replace("<project>", slug).replace("<Project>", project.name)
        sections, _ = stub_sections(text)
        diff = "".join(
            difflib.unified_diff([], text.splitlines(keepends=True), fromfile="/dev/null", tofile=str(target))
        )
        proposals.append(
            {
                **proposal,
                "stub": str(stub),
                "action": "create",
                "diff": diff,
                "text": text if contract.writes_allowed else None,
                **_section_split(sections, depth),
            }
        )
    return proposals


_LEARNING_HEADING = re.compile(r"^#{2,3}[ \t]+learning\b.*$", re.IGNORECASE | re.MULTILINE)


def _learning_bounds(text: str) -> tuple[int, int] | None:
    match = _LEARNING_HEADING.search(text)
    if not match:
        return None
    level = len(match.group(0)) - len(match.group(0).lstrip("#"))
    following = re.compile(rf"^#{{1,{level}}}[ \t]", re.MULTILINE)
    end = following.search(text, match.end())
    return match.start(), end.start() if end else len(text)


def learning_section(text: str) -> str:
    """Return the learning section of an entry file, or ``""``."""
    bounds = _learning_bounds(text)
    return text[bounds[0]:bounds[1]].rstrip() + "\n" if bounds else ""


def audit_learning_section(text: str | None) -> dict[str, Any]:
    """Read-only. Learning is optional spine: absence means learn is report-only."""
    if text is None or not learning_section(text):
        return {
            "check": "learning",
            "status": "N/A",
            "fact": "AGENTS.md declares no learning section, so learn is report-only",
            "recommendation": "optional: merge the Learning section from templates/AGENTS.md to queue proposals",
        }
    try:
        location = queue_location(text)
    except ValueError as error:
        return {"check": "learning", "status": "DEGRADED", "fact": str(error),
                "recommendation": "keep one `proposal-queue:` line"}
    if location is None:
        return {
            "check": "learning",
            "status": "N/A",
            "fact": "learning section declares no proposal-queue, so learn is report-only",
            "recommendation": "",
        }
    errors = queue_location_errors(location)
    if errors:
        return {"check": "learning", "status": "DEGRADED", "fact": "; ".join(errors),
                "recommendation": "move the proposal queue out of any skills directory, relative to the root"}
    return {"check": "learning", "status": "OK", "fact": f"proposals queue at {location}", "recommendation": ""}


def ensure_learning_section(text: str, template: str) -> str:
    """Merge the template's Learning section; never replaces a project's own.

    Not a required spine section: apply offers it, audit never reports its absence as drift.
    """
    if _learning_bounds(text):
        return text
    section = learning_section(template)
    if not section:
        raise ValueError("template carries no learning section")
    anchor = _TRIPWIRES_HEADING.search(text)
    if anchor:
        return text[:anchor.start()] + section + "\n" + text[anchor.start():]
    return text.rstrip("\n") + "\n\n" + section


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    checks = parser.add_mutually_exclusive_group(required=True)
    checks.add_argument("--check-reporting", metavar="AGENTS_MD", type=pathlib.Path,
                        help="read-only: report whether this entry file carries the reporting contract")
    checks.add_argument("--check-learning", metavar="AGENTS_MD", type=pathlib.Path,
                        help="read-only: report the declared proposal queue (optional section)")
    checks.add_argument("--check-moved-skills", metavar="FILE", type=pathlib.Path,
                        help="read-only: propose updates for references to skills that moved to a pack")
    args = parser.parse_args(argv)
    if args.check_moved_skills:
        path = args.check_moved_skills
        proposals = audit_moved_skill_references(path.read_text(encoding="utf-8")) if path.is_file() else []
        for proposal in proposals:
            print(
                f"moved-skill | {path}:{proposal['line']} | {proposal['from']} -> {proposal['to']} | "
                f"install pack {proposal['pack']}"
            )
        return 1 if proposals else 0
    if args.check_learning:
        path = args.check_learning
        finding = audit_learning_section(path.read_text(encoding="utf-8") if path.is_file() else None)
        print(f"{finding['check']} | {finding['status']} | {finding['fact']} | {finding['recommendation']} | {path}")
        return 1 if finding["status"] == "DEGRADED" else 0
    path: pathlib.Path = args.check_reporting
    text = path.read_text(encoding="utf-8") if path.is_file() else None
    finding = audit_reporting_contract(text)
    print(f"{finding['check']} | {finding['status']} | {finding['fact']} | {finding['recommendation']} | {path}")
    return 0 if finding["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
