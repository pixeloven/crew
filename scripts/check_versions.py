#!/usr/bin/env python3
"""Every version source in the repo must name the same version.

One semver line drives all consumers (docs/MAINTAINERS.md, Versioning), but it
is written down in more than one place. Claude Code re-fetches on
.claude-plugin/plugin.json, npm and pi.dev read package.json, and pinned
consumers read the git tag. ci.yml's version-bump gate only proves plugin.json
moved; this proves nothing else was left behind.

    check_versions.py [ROOT]                # default: this repo
    check_versions.py --tag vX.Y.Z [ROOT]   # also compare a git tag

REQUIRED sources must exist and carry a `version`. Any other harness manifest
(`.<harness>-plugin/plugin.json`, e.g. .codex-plugin or .cursor-plugin) joins
the comparison when it carries a top-level `version` and is skipped when it
does not -- some harnesses version from the tag alone.

Packs folded into the repo under `packs/<name>/` ride the same release line:
each pack's manifests join the comparison (a pack needs at least one), and a
pack skill's `plugin:crew@>=X.Y.Z` floor may not name a version above the
repo's -- the pack and the Crew it needs ship in the same commit. A root with
no `packs/` directory (an external pack checked by pack-checks.yml) is checked
exactly as before."""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRED = ("package.json", ".claude-plugin/plugin.json")
OPTIONAL_GLOB = ".*-plugin/plugin.json"
PACKS_DIR = "packs"
PACK_MANIFESTS = ("package.json", ".claude-plugin/plugin.json")
CREW_FLOOR = re.compile(r"plugin:crew@>=(\d+)\.(\d+)\.(\d+)\b")


def sources(root: pathlib.Path) -> tuple[dict[str, str], list[str]]:
    """Return ({source: version}, errors)."""
    found, errors = {}, []
    optional = sorted(p.relative_to(root).as_posix() for p in root.glob(OPTIONAL_GLOB))
    for rel in dict.fromkeys([*REQUIRED, *optional]):
        path = root / rel
        if not path.is_file():
            errors.append(f"{rel}: missing")
            continue
        try:
            version = json.loads(path.read_text(encoding="utf-8")).get("version")
        except (json.JSONDecodeError, AttributeError) as exc:
            errors.append(f"{rel}: not a JSON object ({exc})")
            continue
        if isinstance(version, str) and version:
            found[rel] = version
        elif rel in REQUIRED:
            errors.append(f"{rel}: no `version`")
    for pack in pack_roots(root):
        prefix = pack.relative_to(root).as_posix()
        manifests = sorted(
            {*(rel for rel in PACK_MANIFESTS if (pack / rel).is_file()),
             *(p.relative_to(pack).as_posix() for p in pack.glob(OPTIONAL_GLOB))}
        )
        if not manifests:
            errors.append(f"{prefix}: no manifest (package.json or .claude-plugin/plugin.json)")
        for rel in manifests:
            try:
                version = json.loads((pack / rel).read_text(encoding="utf-8")).get("version")
            except (json.JSONDecodeError, AttributeError) as exc:
                errors.append(f"{prefix}/{rel}: not a JSON object ({exc})")
                continue
            if isinstance(version, str) and version:
                found[f"{prefix}/{rel}"] = version
            elif rel in PACK_MANIFESTS:
                errors.append(f"{prefix}/{rel}: no `version`")
    return found, errors


def pack_roots(root: pathlib.Path) -> list[pathlib.Path]:
    """Every directory under packs/, sorted. Empty when the root folds no packs."""
    base = root / PACKS_DIR
    return sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


def floors_above(root: pathlib.Path, version: str) -> list[str]:
    """Pack skills whose `plugin:crew@>=` floor exceeds the repo version."""
    try:
        current = tuple(int(part) for part in version.split("-", 1)[0].split("+", 1)[0].split("."))
    except ValueError:
        return []
    problems = []
    for pack in pack_roots(root):
        for skill in sorted(pack.glob("skills/*/SKILL.md")):
            text = skill.read_text(encoding="utf-8")
            for match in CREW_FLOOR.finditer(text):
                floor = tuple(int(part) for part in match.groups())
                if floor > current:
                    problems.append(
                        f"{skill.relative_to(root).as_posix()}: plugin:crew@>={'.'.join(match.groups())} "
                        f"is above the repo version {version}"
                    )
    return problems


def main(argv: list[str]) -> int:
    tag = None
    if argv[:1] == ["--tag"]:
        if len(argv) < 2:
            print("usage: check_versions.py [--tag vX.Y.Z] [ROOT]")
            return 2
        tag, argv = argv[1], argv[2:]
    root = pathlib.Path(argv[0]) if argv else ROOT

    found, errors = sources(root)
    if tag is not None:
        found["git tag"] = tag.removeprefix("v")
    listing = "\n".join(f"  {name}: {version}" for name, version in found.items())
    if errors:
        print("\n".join(errors))
        print(f"\nVersion sources read so far:\n{listing}")
        return 1
    if len(set(found.values())) > 1:
        print(f"Version sources disagree:\n{listing}")
        print("\nBump them together -- consumers on different harnesses must receive the same release.")
        return 1
    agreed = next(iter(found.values()))
    above = floors_above(root, agreed)
    if above:
        print("\n".join(above))
        print("\nA folded pack ships with the Crew in the same commit; lower the floor or bump the version.")
        return 1
    print(f"{len(found)} version sources agree on {agreed}:\n{listing}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
