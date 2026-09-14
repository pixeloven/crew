#!/usr/bin/env python3
"""Validate plugin manifests and SKILL.md frontmatter against schema v2.

Schema v2 fields (exactly these, in any order):
  name         must equal the skill's directory name
  description  trigger language; MIN_DESC..MAX_DESC chars — for skills no agent
               always-loads, the description is the only load path. The maximum
               is this repository's tested policy, not a frozen harness limit.
  tier         concept | subject
  requires     [] | list of mcp:<group> / cluster / external:github / external:web / cli:<tool>
  expects-local  OPTIONAL — the consumer-local skill slots this skill defers to
               (see templates/local-skills/README.md); the onboarding doctor
               reports unfilled slots

Legacy fields (category, durability) are forbidden — they carried no signal.
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
REQUIRES_RE = re.compile(r"^(mcp:[a-z0-9-]+|cluster|external:(github|web)|cli:[a-z0-9-]+)$")
ALLOWED_FIELDS = {"name", "description", "tier", "requires", "expects-local"}
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


def yaml_module():
    try:
        import yaml
    except ImportError:
        import subprocess

        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
        import yaml
    return yaml


def validate_root(root: pathlib.Path) -> list[str]:
    yaml = yaml_module()
    errors: list[str] = []
    root = pathlib.Path(root)

    for m in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "package.json"]:
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
        if "expects-local" in fm:
            slots = fm["expects-local"]
            if not (isinstance(slots, list) and slots and set(slots) <= LOCAL_SLOT_VOCABULARY):
                errors.append(
                    f"{rel}: expects-local must be a non-empty subset of "
                    f"{sorted(LOCAL_SLOT_VOCABULARY)}, got {slots!r}"
                )

    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=pathlib.Path, default=ROOT, help="package root (default: script parent)")
    args = parser.parse_args()
    errors = validate_root(args.root.resolve())

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print(
        "manifests valid; all SKILL.md frontmatter conforms to schema v2 "
        f"and the {MAX_DESC}-character description budget"
    )


if __name__ == "__main__":
    main()
