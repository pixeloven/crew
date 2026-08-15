#!/usr/bin/env python3
"""Validate plugin manifests and SKILL.md frontmatter against schema v2.

Schema v2 fields (exactly these, in any order):
  name         must equal the skill's directory name
  description  trigger language; >= MIN_DESC chars — for skills no agent
               always-loads, the description is the only load path
  tier         concept | subject
  requires     [] | list of mcp:<group> / cluster / external:github / external:web / cli:<tool>
  expects-local  OPTIONAL — the consumer-local skill slots this skill defers to
               (see templates/local-skills/README.md); the onboarding doctor
               reports unfilled slots

Legacy fields (category, durability) are forbidden — they carried no signal.
"""

import glob
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIN_DESC = 110
TIERS = {"concept", "subject"}
REQUIRES_RE = re.compile(r"^(mcp:[a-z0-9-]+|cluster|external:(github|web)|cli:[a-z0-9-]+)$")
ALLOWED_FIELDS = {"name", "description", "tier", "requires", "expects-local"}
# Canonical consumer-local slot names — documented in templates/local-skills/README.md,
# each with a starter stub in that directory.
LOCAL_SLOTS = {
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


def main():
    yaml = yaml_module()
    errors = []

    for m in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "package.json"]:
        try:
            json.loads((ROOT / m).read_text())
        except Exception as e:
            errors.append(f"{m}: invalid JSON: {e}")

    plugin_ver = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]
    pkg_ver = json.loads((ROOT / "package.json").read_text())["version"]
    if plugin_ver != pkg_ver:
        errors.append(f"version drift: plugin.json {plugin_ver} != package.json {pkg_ver}")

    for skill in sorted(glob.glob(str(ROOT / "skills/*/SKILL.md"))):
        rel = str(pathlib.Path(skill).relative_to(ROOT))
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
            if not (isinstance(slots, list) and slots and set(slots) <= LOCAL_SLOTS):
                errors.append(
                    f"{rel}: expects-local must be a non-empty subset of {sorted(LOCAL_SLOTS)}, got {slots!r}"
                )

    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("manifests valid; all SKILL.md frontmatter conforms to schema v2")


if __name__ == "__main__":
    main()
