#!/usr/bin/env python3
"""Assert that every skill sits where the harnesses actually look.

This is the check that did not exist when it was needed. Six places in this
foundation taught that Claude Code wants a flat `.claude/skills/<name>.md`; a
consumer followed that and ran 26 local skills invisible to every Claude Code
session for months, with no error anywhere. Frontmatter validation would not
have caught it -- the frontmatter was fine. The *layout* was wrong.

Deliberately narrow. Reach for the harness's own tooling first -- it is
maintained alongside the runtime that has to read these files:

    claude plugin validate <path> --strict     manifests, frontmatter, and the
                                               rule that plugin components are
                                               read WITHOUT following symlinks
    claude --plugin-dir <path> plugin details <name>
                                               component inventory and projected
                                               token cost, per component
    codex debug prompt-input "hi"              the model-visible skill listing,
                                               rendered with no API call

This covers only what those do not. Verified against `claude plugin validate
--strict`, which PASSES a plugin containing both a flat `skills/<name>.md` and a
`name:` disagreeing with its directory -- the two faults that actually shipped.

Also separate from check_skills.py, which enforces this foundation's CATALOGUE
schema (tier, requires, expects-local). That schema is ours; a consumer's local
skills are not obliged to it.

    check_skill_layout.py [ROOT]        # default: cwd
    check_skill_layout.py --selftest    # prove the checks can fail

Every skill, everywhere, is a directory containing SKILL.md:

    .agents/skills/<name>/SKILL.md          pi and Codex read this natively
    .claude/skills/<name>/SKILL.md          Claude Code (usually a symlink)
    skills/<name>/SKILL.md                  what a distributed plugin ships
"""

import argparse
import pathlib
import re
import sys
import tempfile

# Where each harness looks. A flat `<name>.md` in any of these is invisible to
# the harness that reads it -- silently, which is the whole problem.
SKILL_DIRS = (".agents/skills", ".claude/skills", "skills")

NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.M)
DESC_RE = re.compile(r"^description:\s*(.+)$", re.M)


def check(root: pathlib.Path) -> list[str]:
    errors: list[str] = []

    for rel in SKILL_DIRS:
        base = root / rel
        if not base.is_dir():
            continue

        for entry in sorted(base.iterdir()):
            # A dangling symlink is the failure mode that actually bit: the
            # tree looks right, `ls` shows the name, and the target is gone.
            if entry.is_symlink() and not entry.exists():
                errors.append(f"{rel}/{entry.name}: dangling symlink -> {entry.readlink()}")
                continue

            if entry.is_file() and entry.suffix == ".md":
                if entry.name.upper() == "README.MD":
                    continue
                errors.append(
                    f"{rel}/{entry.name}: flat file. Every harness wants "
                    f"{rel}/{entry.stem}/SKILL.md -- a flat file is invisible "
                    f"to Claude Code with no error"
                )
                continue

            if not entry.is_dir():
                continue

            skill = entry / "SKILL.md"
            if not skill.is_file():
                errors.append(f"{rel}/{entry.name}/: no SKILL.md")
                continue

            text = skill.read_text(encoding="utf-8")
            m = NAME_RE.search(text)
            if not m:
                errors.append(f"{rel}/{entry.name}/SKILL.md: no `name:` in frontmatter")
            elif m.group(1) != entry.name:
                errors.append(
                    f"{rel}/{entry.name}/SKILL.md: name is {m.group(1)!r} "
                    f"but the directory is {entry.name!r} -- the directory wins, "
                    f"so the skill loads under a name nothing routes to"
                )

            if not DESC_RE.search(text):
                errors.append(f"{rel}/{entry.name}/SKILL.md: no `description:` — it is the entire load path")

    return errors


def selftest() -> int:
    """A gate is only proven by watching it reject something."""
    cases = []
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp)
        good = root / ".agents/skills/well-formed"
        good.mkdir(parents=True)
        (good / "SKILL.md").write_text("---\nname: well-formed\ndescription: fine\n---\n")
        cases.append(("a well-formed skill passes", not check(root)))

        flat = root / ".claude/skills"
        flat.mkdir(parents=True)
        (flat / "legacy.md").write_text("---\nname: legacy\ndescription: flat\n---\n")
        cases.append(("a flat .md is rejected", any("flat file" in e for e in check(root))))
        (flat / "legacy.md").unlink()

        (flat / "gone").symlink_to(root / ".agents/skills/missing")
        cases.append(("a dangling symlink is rejected", any("dangling" in e for e in check(root))))
        (flat / "gone").unlink()

        nodesc = root / ".agents/skills/nodesc"
        nodesc.mkdir(parents=True)
        (nodesc / "SKILL.md").write_text("---\nname: nodesc\n---\n")
        cases.append(("a missing description is rejected", any("no `description:`" in e for e in check(root))))
        (nodesc / "SKILL.md").unlink(); nodesc.rmdir()

        bad = root / ".agents/skills/misnamed"
        bad.mkdir(parents=True)
        (bad / "SKILL.md").write_text("---\nname: something-else\ndescription: x\n---\n")
        cases.append(("a name/directory mismatch is rejected", any("but the directory is" in e for e in check(root))))

    for label, ok in cases:
        print(f"{'ok  ' if ok else 'FAIL'} {label}")
    return 0 if all(ok for _, ok in cases) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="repository root (default: cwd)")
    ap.add_argument("--selftest", action="store_true", help="prove the checks can fail")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    root = pathlib.Path(args.root).resolve()
    if not any((root / d).is_dir() for d in SKILL_DIRS):
        print(f"no skill directories under {root} ({', '.join(SKILL_DIRS)})", file=sys.stderr)
        return 1

    errors = check(root)
    for e in errors:
        print(f"{root.name}: {e}", file=sys.stderr)
    if errors:
        print(f"\n{len(errors)} layout problem(s). Verify against the running harness, "
              f"not the file tree -- the tree looks right in exactly the case that fails.",
              file=sys.stderr)
        return 1
    print("skill layout ok: every skill is <name>/SKILL.md where its harness looks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
