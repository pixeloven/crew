#!/usr/bin/env python3
"""Validate plugin manifests and SKILL.md frontmatter against schema v2.

Schema v2 fields (exactly these, in any order):
  name         must equal the skill's directory name
  description  trigger language; MIN_DESC..MAX_DESC chars — for skills no agent
               always-loads, the description is the only load path. The maximum
               is this repository's tested policy, not a frozen harness limit.
  tier         concept | subject
  requires     [] | list of mcp:<group> / cluster / external:github / external:web /
               cli:<tool> / plugin:<name>@>=X.Y.Z (a pack's dependency on crew)
  expects-local  OPTIONAL — the consumer-local skill slots this skill defers to
               (see templates/local-skills/README.md); the onboarding doctor
               reports unfilled slots
  provides     OPTIONAL, packs only — the slots this skill fills; each must be
               listed in roles/expected-local-skills.txt or the pack's own
               slots.txt. Crew itself fills none.

Legacy fields (category, durability) are forbidden — they carried no signal.

Pack mode (`--root <pack> --pack`) runs this same gate against a sibling pack's
skills (see docs/PACKS.md). Crew's slot list always comes from THIS crew install,
never from the pack, so a pack cannot widen Crew's vocabulary. A pack may declare
slots of its own in `slots.txt` at its root (same format as
roles/expected-local-skills.txt); those widen `expects-local` and `provides` for
that pack only, and must be kebab-case, unique, not a Crew slot name, stubbed at
`templates/local-skills/<slot>.md`, and deferred to by at least one pack skill.
Crew mode never reads a `slots.txt`. Both modes check the section-marker grammar
(`crew:discoverable`, `crew:optional`) of every stub in `templates/local-skills/`,
and both warn, without failing, on an `mcp:` name in `requires:` or a
`crew:discoverable` marker that is not in Crew's docs/capabilities.txt
(docs/CAPABILITIES.md). `--report-cost` prints always-on description sizes; it never affects the exit code.

Local mode (`--local <consumer-root>`) checks a consumer's learned skills: only
`.agents/skills/*/SKILL.md` (and `.claude/skills/`) files carrying a
`<!-- crew:learned ... -->` marker (docs/LEARNING.md), against this same schema.
A hand-written local skill is not obliged to Crew's catalogue schema; a learned one
is, because Crew's gate is what promoted it. Stdlib only, via frontmatter.py.
"""

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIN_DESC = 110
MAX_DESC = 300
TIERS = {"concept", "subject"}
REQUIRES_RE = re.compile(
    r"^(mcp:[a-z0-9-]+|cluster|external:(github|web)|cli:[a-z0-9-]+"
    r"|plugin:[a-z0-9-]+@>=(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*))$"
)
CREW_REQUIREMENT = "plugin:crew@>="
ALLOWED_FIELDS = {"name", "description", "tier", "requires", "expects-local", "provides"}
# A pack is skills only: crew's roles pick its skills up through slots.
PACK_FORBIDDEN_DIRS = ("roles", "agents", "pi-agents")
# Canonical consumer-local vocabulary — documented in templates/local-skills/README.md,
# each with a starter stub. Doctor derives required slots from actual
# `expects-local` declarations; it does not treat every vocabulary term as required.
LOCAL_SLOT_VOCABULARY = {
    "platform-conventions",
    "topology",
    "protected-seams",
    "litellm-access-map",
    "secret-paths",
    "vault-ops",
    "agent-runtime",
    "decision-record-format",
}


# A slot name is plain kebab-case: never prefixed with its pack's name.
SLOT_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PACK_SLOTS_FILE = "slots.txt"
PACK_SLOT_STUBS = "templates/local-skills"


def slot_lines(path: pathlib.Path) -> list[str]:
    """Slot names in a slot list, in file order: one per line, `#` comments skipped."""
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


# Stub section markers (docs/PACKS.md, "Marking stub sections"). A marker sits alone
# on a line inside a section: the lines under one ATX heading, up to the next
# heading of any level. `▸ Fill` in a section means it still needs content.
FILL_MARKER = "▸ Fill"
STUB_MARKER_PREFIX = re.compile(r"^\s*<!--\s*crew:(discoverable|optional)\b")
DISCOVERABLE_MARKER = re.compile(r"^\s*<!--\s*crew:discoverable\s+capability=(\S+)\s*-->\s*$")
OPTIONAL_MARKER = re.compile(r"^\s*<!--\s*crew:optional\s*-->\s*$")
STUB_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$")
STUB_FENCE = re.compile(r"^\s*(```|~~~)")


def stub_sections(text: str) -> tuple[list[dict], list[str]]:
    """A stub's (or fill's) sections, their markers and fill state, and grammar errors.

    Each section is {heading, level, discoverable, capabilities, optional,
    unfilled}. `capabilities` lists every discoverable marker in order (any one of
    them can supply the section); `discoverable` is the first, or None. Each
    capability uses the `requires:` vocabulary, minus `plugin:` (a
    plugin is a dependency, not a source of facts). Fenced code is skipped, and so
    is a leading frontmatter block. Content before the first heading belongs to no
    section; a marker there is an error.
    """
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
        if closing is not None:
            lines = lines[closing + 1:]
    sections: list[dict] = []
    errors: list[str] = []
    fence = None
    for number, line in enumerate(lines, 1):
        opener = STUB_FENCE.match(line)
        if fence:
            if opener and opener.group(1) == fence:
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue
        heading = STUB_HEADING.match(line)
        if heading:
            sections.append(
                {"heading": heading.group(2), "level": len(heading.group(1)),
                 "discoverable": None, "capabilities": [], "optional": False, "unfilled": False}
            )
            continue
        current = sections[-1] if sections else None
        if FILL_MARKER in line and current:
            current["unfilled"] = True
        if not STUB_MARKER_PREFIX.match(line):
            continue
        if current is None:
            errors.append(f"line {number}: section marker before the first heading belongs to no section")
            continue
        discoverable = DISCOVERABLE_MARKER.match(line)
        if discoverable:
            capability = discoverable.group(1)
            if capability.startswith("plugin:") or not REQUIRES_RE.match(capability):
                errors.append(
                    f"line {number}: discoverable capability {capability!r} must be a requires: capability "
                    "(mcp:<group>, cli:<tool>, external:github|web, cluster)"
                )
            elif capability in current["capabilities"]:
                errors.append(f"line {number}: section {current['heading']!r} repeats discoverable capability {capability!r}")
            else:
                current["capabilities"].append(capability)
                current["discoverable"] = current["discoverable"] or capability
        elif OPTIONAL_MARKER.match(line):
            current["optional"] = True
        else:
            errors.append(f"line {number}: malformed section marker {line.strip()!r}")
    return sections, errors


def stub_marker_errors(root: pathlib.Path) -> list[str]:
    """Grammar errors in every stub under `templates/local-skills/`, by path."""
    errors: list[str] = []
    for stub in sorted((pathlib.Path(root) / PACK_SLOT_STUBS).glob("*.md")):
        if stub.name == "README.md":
            continue
        _, found = stub_sections(stub.read_text(encoding="utf-8"))
        rel = f"{PACK_SLOT_STUBS}/{stub.name}"
        errors.extend(f"{rel}: {error}" for error in found)
    return errors


# Capability vocabulary (docs/CAPABILITIES.md). Always read from THIS crew install,
# like the slot list. Unknown `mcp:` names warn, never fail: a pack may need a
# source the vocabulary lacks, and the fix is a PR to the vocabulary.
CAPABILITY_VOCABULARY_FILE = ROOT / "docs" / "capabilities.txt"
CAPABILITY_DOC = "docs/CAPABILITIES.md"


def capability_vocabulary(path: pathlib.Path = CAPABILITY_VOCABULARY_FILE) -> set[str]:
    """Crew's shared capability names, one per line in docs/capabilities.txt."""
    return set(slot_lines(path))


def capability_warnings(root: pathlib.Path) -> list[str]:
    """`mcp:` names in `requires:` or `crew:discoverable` markers outside the vocabulary.

    Advisory only: the caller prints these and keeps its exit code. Malformed
    frontmatter or markers are validate_root's errors, so they are skipped here.
    """
    yaml = yaml_module()
    root = pathlib.Path(root)
    known = capability_vocabulary()
    found: list[tuple[str, str]] = []
    for skill_path in sorted(root.glob("skills/*/SKILL.md")):
        try:
            fm = yaml.safe_load(skill_path.read_text(encoding="utf-8").split("---", 2)[1])
        except Exception:
            continue
        requires = fm.get("requires") if isinstance(fm, dict) else None
        for name in requires if isinstance(requires, list) else []:
            if isinstance(name, str):
                found.append((str(skill_path.relative_to(root)), name))
    for stub in sorted((root / PACK_SLOT_STUBS).glob("*.md")):
        if stub.name == "README.md":
            continue
        sections, _ = stub_sections(stub.read_text(encoding="utf-8"))
        rel = f"{PACK_SLOT_STUBS}/{stub.name}"
        found.extend((rel, name) for section in sections for name in section["capabilities"])
    return [
        f"warning: {rel}: {name} is not in Crew's capability vocabulary ({CAPABILITY_DOC}); "
        "reuse a listed name or propose one there"
        for rel, name in found
        if name.startswith("mcp:") and name not in known
    ]


def expected_local_slots(path: pathlib.Path = ROOT / "roles" / "expected-local-skills.txt") -> set[str]:
    """Slot names crew's roles cite — the only crew names a `provides:` may fill."""
    return set(slot_lines(path))


def pack_slots(root: pathlib.Path) -> tuple[set[str], list[str]]:
    """A pack's own declared slots (its `slots.txt`) and the errors in that list.

    No `slots.txt` declares none, which is valid. Crew's names are reserved: a pack
    that reuses one would make a fill ambiguous between two contracts.
    """
    path = pathlib.Path(root) / PACK_SLOTS_FILE
    if not path.is_file():
        return set(), []
    crew_slots = LOCAL_SLOT_VOCABULARY | expected_local_slots()
    declared: set[str] = set()
    errors: list[str] = []
    for slot in slot_lines(path):
        if not SLOT_NAME_RE.fullmatch(slot):
            errors.append(f"{PACK_SLOTS_FILE}: slot {slot!r} must be plain kebab-case (no pack prefix)")
            continue
        if slot in declared:
            errors.append(f"{PACK_SLOTS_FILE}: duplicate slot {slot!r}")
            continue
        if slot in crew_slots:
            errors.append(f"{PACK_SLOTS_FILE}: {slot!r} is a crew slot; a pack declares only slots of its own")
            continue
        declared.add(slot)
        stub = f"{PACK_SLOT_STUBS}/{slot}.md"
        if not (pathlib.Path(root) / stub).is_file():
            errors.append(f"{PACK_SLOTS_FILE}: slot {slot!r} has no stub template at {stub}")
    return declared, errors


def yaml_module():
    try:
        import yaml
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
        import yaml
    return yaml


def skill_field_errors(
    rel: str, fm: dict, dirname: str, provides_slots: set[str], own_slots: frozenset[str] = frozenset()
) -> tuple[list[str], bool]:
    """Schema-v2 field errors for one parsed frontmatter mapping, and whether it
    declares a crew dependency. Shared by catalogue, pack, and --local modes.
    `own_slots` is a pack's `slots.txt`; it widens expects-local and provides."""
    errors: list[str] = []
    declares_crew = False
    unknown = set(fm) - ALLOWED_FIELDS
    if unknown:
        errors.append(f"{rel}: unknown/legacy frontmatter fields {sorted(unknown)}")
    if fm.get("name") != dirname:
        errors.append(f"{rel}: name '{fm.get('name')}' != directory '{dirname}'")
    desc = fm.get("description") or ""
    if len(desc) < MIN_DESC:
        errors.append(f"{rel}: description too short ({len(desc)} < {MIN_DESC} chars) — it's the load path")
    if len(desc) > MAX_DESC:
        errors.append(
            f"{rel}: description too long ({len(desc)} > {MAX_DESC} chars) — "
            "the repository policy preserves trigger language under catalogue pressure"
        )
    if fm.get("tier") not in TIERS:
        errors.append(f"{rel}: tier must be one of {sorted(TIERS)}, got {fm.get('tier')!r}")
    req = fm.get("requires")
    if not isinstance(req, list):
        errors.append(f"{rel}: requires must be a list (may be empty)")
    else:
        for r in req:
            if not (isinstance(r, str) and REQUIRES_RE.match(r)):
                errors.append(f"{rel}: invalid requires entry {r!r}")
            elif r.startswith(CREW_REQUIREMENT):
                declares_crew = True
    if "expects-local" in fm:
        slots = fm["expects-local"]
        accepted = LOCAL_SLOT_VOCABULARY | own_slots
        if not (isinstance(slots, list) and slots and set(slots) <= accepted):
            errors.append(
                f"{rel}: expects-local must be a non-empty subset of "
                f"{sorted(accepted)}{' (crew + slots.txt)' if own_slots else ''}, got {slots!r}"
            )
    if "provides" in fm:
        slots = fm["provides"]
        accepted = provides_slots | own_slots
        source = "roles/expected-local-skills.txt" + (" + slots.txt" if own_slots else "")
        if not (isinstance(slots, list) and slots and set(slots) <= accepted):
            errors.append(
                f"{rel}: provides must be a non-empty subset of "
                f"{sorted(accepted)} ({source}), got {slots!r}"
            )
    return errors, declares_crew


def validate_root(root: pathlib.Path, *, pack: bool = False) -> list[str]:
    yaml = yaml_module()
    errors: list[str] = []
    root = pathlib.Path(root)
    provides_slots = expected_local_slots()
    undeclared: list[str] = []
    # Crew mode never reads a slots.txt: crew's slots are roles/expected-local-skills.txt.
    own_slots: set[str] = set()
    deferred_to: set[str] = set()

    manifests = [".claude-plugin/plugin.json", "package.json"]
    if pack:
        # A pack may target one harness, so it needs a manifest, not both.
        manifests = [m for m in manifests if (root / m).exists()]
        if not manifests:
            errors.append("pack has no manifest: expected .claude-plugin/plugin.json and/or package.json")
        for d in PACK_FORBIDDEN_DIRS:
            if (root / d).exists():
                errors.append(f"{d}/: a pack ships no roles — crew's roles pick its skills up through slots")
        own_slots, slot_errors = pack_slots(root)
        errors.extend(slot_errors)
    errors.extend(stub_marker_errors(root))
    for m in manifests:
        try:
            json.loads((root / m).read_text())
        except Exception as e:
            errors.append(f"{m}: invalid JSON: {e}")

    try:
        plugin_ver = json.loads((root / ".claude-plugin/plugin.json").read_text())["version"]
        pkg_ver = json.loads((root / "package.json").read_text())["version"]
        if plugin_ver != pkg_ver:
            errors.append(f"version drift: plugin.json {plugin_ver} != package.json {pkg_ver}")
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        pass

    for skill_path in sorted(root.glob("skills/*/SKILL.md")):
        skill = str(skill_path)
        rel = str(skill_path.relative_to(root))
        dirname = pathlib.Path(skill).parent.name
        text = pathlib.Path(skill).read_text()
        if not text.startswith("---"):
            errors.append(f"{rel}: missing YAML frontmatter")
            continue
        try:
            fm = yaml.safe_load(text.split("---", 2)[1])
        except Exception as e:
            errors.append(f"{rel}: frontmatter not valid YAML: {e}")
            continue
        if not isinstance(fm, dict):
            errors.append(f"{rel}: frontmatter must be a mapping")
            continue
        field_errors, declares_crew = skill_field_errors(rel, fm, dirname, provides_slots, frozenset(own_slots))
        errors.extend(field_errors)
        if isinstance(fm.get("expects-local"), list):
            deferred_to.update(slot for slot in fm["expects-local"] if isinstance(slot, str))
        if pack and not declares_crew:
            # Every skill, not any: a skill is installed, listed, and moved on
            # its own, so each one carries the Crew it was checked against.
            undeclared.append(rel)

    for rel in undeclared:
        errors.append(f"{rel}: pack skill declares no crew dependency: add {CREW_REQUIREMENT}X.Y.Z to its requires")
    for slot in sorted(own_slots - deferred_to):
        # A declared slot nothing defers to is a fill no skill reads.
        errors.append(f"{PACK_SLOTS_FILE}: slot {slot!r} is in no pack skill's expects-local")
    return errors


LOCAL_SKILL_DIRS = (".agents/skills", ".claude/skills")


def validate_local(consumer_root: pathlib.Path) -> tuple[list[str], int]:
    """Validate only the learned skills under a consumer root; return errors and count."""
    try:
        from .frontmatter import read_frontmatter
        from .learn_contract import learned_markers
    except ImportError:  # Direct script execution.
        from frontmatter import read_frontmatter
        from learn_contract import learned_markers

    root = pathlib.Path(consumer_root)
    provides_slots = expected_local_slots()
    errors: list[str] = []
    seen: set[pathlib.Path] = set()
    count = 0
    for rel_dir in LOCAL_SKILL_DIRS:
        for skill_path in sorted((root / rel_dir).glob("*/SKILL.md")):
            resolved = skill_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            rel = skill_path.relative_to(root).as_posix()
            markers, marker_errors = learned_markers(skill_path.read_text(encoding="utf-8"))
            if not markers and not marker_errors:
                continue
            count += 1
            errors.extend(f"{rel}: {error}" for error in marker_errors)
            fm, error = read_frontmatter(skill_path)
            if error:
                errors.append(f"{rel}: {error}")
                continue
            field_errors, _ = skill_field_errors(rel, fm, skill_path.parent.name, provides_slots)
            errors.extend(field_errors)
            if "provides" in fm:
                errors.append(f"{rel}: provides is pack-only; a local skill fills a slot by its name")
    return errors, count


def description_costs(root: pathlib.Path) -> list[tuple[str, int]]:
    """Always-on cost: every listed skill's description is paid every session."""
    yaml = yaml_module()
    costs: list[tuple[str, int]] = []
    for skill_path in sorted(pathlib.Path(root).glob("skills/*/SKILL.md")):
        try:
            fm = yaml.safe_load(skill_path.read_text().split("---", 2)[1])
        except Exception:
            fm = None
        desc = fm.get("description") if isinstance(fm, dict) else None
        costs.append((skill_path.parent.name, len(desc) if isinstance(desc, str) else 0))
    return costs


def print_cost_report(root: pathlib.Path) -> None:
    # A report, never a gate: the budget is the operator's to spend, not ours to cap.
    costs = description_costs(root)
    width = max((len(name) for name, _ in costs), default=0)
    for name, chars in costs:
        print(f"{name.ljust(width)}  {chars}")
    total = sum(chars for _, chars in costs)
    print(f"total always-on description chars: {total} ({len(costs)} skills)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=ROOT, help="package root (default: script parent)")
    parser.add_argument("--pack", action="store_true", help="validate --root as a pack (docs/PACKS.md)")
    parser.add_argument(
        "--report-cost", action="store_true", help="print per-skill and total description chars (never fails)"
    )
    parser.add_argument(
        "--local", type=pathlib.Path, metavar="CONSUMER_ROOT",
        help="validate only the learned skills under a consumer root (docs/LEARNING.md)",
    )
    args = parser.parse_args()
    if args.local:
        if args.pack or args.report_cost:
            parser.error("--local runs alone: it checks a consumer's learned skills, not a package")
        errors, count = validate_local(args.local.resolve())
        if errors:
            print("\n".join(errors))
            sys.exit(1)
        print(f"{count} learned skill(s) conform to schema v2 and the {MAX_DESC}-character description budget")
        return
    root = args.root.resolve()
    errors = validate_root(root, pack=args.pack)
    if args.report_cost:
        print_cost_report(root)
    # Warnings never change the exit code.
    for warning in capability_warnings(root):
        print(warning)

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    if args.pack:
        print(f"pack valid; all SKILL.md frontmatter conforms to schema v2 and the {MAX_DESC}-character description budget")
        return
    print(
        "manifests valid; all SKILL.md frontmatter conforms to schema v2 "
        f"and the {MAX_DESC}-character description budget"
    )


if __name__ == "__main__":
    main()
