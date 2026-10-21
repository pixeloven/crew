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
               listed in roles/expected-local-skills.txt. Crew itself fills none.

Legacy fields (category, durability) are forbidden — they carried no signal.

Pack mode (`--root <pack> --pack`) runs this same gate against a sibling pack's
skills (see docs/PACKS.md). The slot list always comes from THIS crew install,
never from the pack, so a pack cannot widen the vocabulary it is checked against.
`--report-cost` prints always-on description sizes; it never affects the exit code.
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
}


def expected_local_slots(path: pathlib.Path = ROOT / "roles" / "expected-local-skills.txt") -> set[str]:
    """Slot names crew's roles cite — the only names a `provides:` may fill."""
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def yaml_module():
    try:
        import yaml
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
        import yaml
    return yaml


def validate_root(root: pathlib.Path, *, pack: bool = False) -> list[str]:
    yaml = yaml_module()
    errors: list[str] = []
    root = pathlib.Path(root)
    provides_slots = expected_local_slots()
    declares_crew = False

    manifests = [".claude-plugin/plugin.json", "package.json"]
    if pack:
        # A pack may target one harness, so it needs a manifest, not both.
        manifests = [m for m in manifests if (root / m).exists()]
        if not manifests:
            errors.append("pack has no manifest: expected .claude-plugin/plugin.json and/or package.json")
        for d in PACK_FORBIDDEN_DIRS:
            if (root / d).exists():
                errors.append(f"{d}/: a pack ships no roles — crew's roles pick its skills up through slots")
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
            if not (isinstance(slots, list) and slots and set(slots) <= LOCAL_SLOT_VOCABULARY):
                errors.append(
                    f"{rel}: expects-local must be a non-empty subset of "
                    f"{sorted(LOCAL_SLOT_VOCABULARY)}, got {slots!r}"
                )
        if "provides" in fm:
            slots = fm["provides"]
            if not (isinstance(slots, list) and slots and set(slots) <= provides_slots):
                errors.append(
                    f"{rel}: provides must be a non-empty subset of "
                    f"{sorted(provides_slots)} (roles/expected-local-skills.txt), got {slots!r}"
                )

    if pack and not declares_crew:
        errors.append(f"pack declares no crew dependency: add requires: [{CREW_REQUIREMENT}X.Y.Z] to its skills")
    return errors


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
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate_root(root, pack=args.pack)
    if args.report_cost:
        print_cost_report(root)

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
