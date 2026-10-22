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
does not -- some harnesses version from the tag alone."""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQUIRED = ("package.json", ".claude-plugin/plugin.json")
OPTIONAL_GLOB = ".*-plugin/plugin.json"


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
    return found, errors


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
    print(f"{len(found)} version sources agree on {next(iter(found.values()))}:\n{listing}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
