#!/usr/bin/env python3
"""Every backticked kebab-case token in agents/ and pi-agents/ bodies that looks
like a skill slug must resolve to skills/<name>/, be a declared expected-local
slot (roles/expected-local-skills.txt), or be a known non-skill token.

This is the guard against shipping agents that reference skills nobody has —
the class of bug fixed in the 0.4.13 correctness sweep."""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN = re.compile(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`")

# Backticked kebab-case tokens that are not skill references (CLI names,
# workflow step names, etc.). Extend deliberately — every entry here is a
# token the checker will never flag again.
NON_SKILL = set()

skills = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
expected_local = {
    line.strip()
    for line in (ROOT / "roles" / "expected-local-skills.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
}

errors = []
for tree in ("agents", "pi-agents"):
    for f in sorted((ROOT / tree).glob("*.md")):
        body = f.read_text().split("---", 2)[-1]
        for tok in TOKEN.findall(body):
            if tok in skills or tok in expected_local or tok in NON_SKILL:
                continue
            errors.append(f"{f.relative_to(ROOT)}: unresolvable skill reference `{tok}`")

if errors:
    print("\n".join(errors))
    print(
        "\nEach token must be a skills/<name>/ dir, an expected-local slot "
        "(roles/expected-local-skills.txt), or a known non-skill token "
        "(NON_SKILL in this script)."
    )
    sys.exit(1)
print(f"skill references resolve across {len(skills)} skills + {len(expected_local)} expected-local slots")
