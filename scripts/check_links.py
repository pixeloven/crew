#!/usr/bin/env python3
"""Every relative Markdown link in shipped/maintained docs must resolve to an
existing path INSIDE the repo.

A link that climbs out with `../` works in a monorepo or sibling checkout and
breaks the moment the plugin is installed on its own -- the installed copy has
nothing above its root. check_skill_refs.py covers skill *names*; this covers
file links.

    check_links.py [ROOT]        # default: this repo

Scanned: top-level *.md plus every *.md under SCAN_DIRS -- what ships (the
package.json `files` trees that carry Markdown) and what maintainers read.
tests/fixtures/ is not scanned: those are synthetic consumer repos whose links
point at files the consumer would own. Pruned anywhere: EXCLUDED_DIRS.

Ignored: links with a scheme (http:, https:, mailto:, ...), protocol-relative
`//host` links, anchor-only `#section` links, and anything inside fenced code
blocks or inline code spans -- those are examples, not links. A `#fragment` on
a relative link is stripped; only the path is checked, not the heading."""

import pathlib
import re
import sys
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCAN_DIRS = ("agents", "docs", "pi-agents", "roles", "skills", "templates")
EXCLUDED_DIRS = {".git", "node_modules", ".remember", ".claude", "__pycache__"}

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)")
# [text](target) / ![alt](target), target optionally <bracketed> and titled.
INLINE = re.compile(r"!?\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)")
# [label]: target -- a reference definition.
REFDEF = re.compile(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]*>|\S+)")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def markdown_files(root: pathlib.Path):
    yield from sorted(root.glob("*.md"))
    for name in SCAN_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            if EXCLUDED_DIRS.isdisjoint(path.relative_to(root).parts):
                yield path


def links(text: str):
    """Yield (line_number, target) for every link outside code."""
    fence = None
    for number, line in enumerate(text.splitlines(), 1):
        opener = FENCE.match(line)
        if fence:
            # A fence closes on the same character, at least as long.
            if opener and opener.group(1)[0] == fence[0] and len(opener.group(1)) >= len(fence):
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue
        line = CODE_SPAN.sub(lambda m: " " * len(m.group(0)), line)
        for pattern in (INLINE, REFDEF):
            for match in pattern.finditer(line):
                yield number, match.group(1).strip("<>")


def check(root: pathlib.Path) -> tuple[list[str], int]:
    real_root = root.resolve()
    errors, checked = [], 0
    for md in markdown_files(root):
        rel_md = md.relative_to(root)
        for number, target in links(md.read_text(encoding="utf-8")):
            if SCHEME.match(target) or target.startswith(("#", "//")):
                continue
            path = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not path:
                continue
            checked += 1
            where = f"{rel_md}:{number}: ({target})"
            if path.startswith("/"):
                errors.append(f"{where} absolute path -- installed copies have no repo root; use a relative link")
                continue
            # resolve() follows symlinks, so a link through one that leaves the
            # repo is caught too.
            resolved = (md.parent / path).resolve()
            if not resolved.is_relative_to(real_root):
                errors.append(f"{where} escapes the repo root -- it breaks once the plugin is installed alone")
            elif not resolved.exists():
                errors.append(f"{where} target does not exist")
    return errors, checked


def main(argv: list[str]) -> int:
    root = pathlib.Path(argv[0]) if argv else ROOT
    errors, checked = check(root)
    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} broken relative link(s). Point each at a path inside the repo.")
        return 1
    print(f"{checked} relative links resolve inside the repo")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
