#!/usr/bin/env python3
"""Dependency-free parsing of the top-level fields Crew validators consume.

Harness-native validators remain responsible for full YAML conformance. These
helpers deliberately parse only the leading frontmatter block and simple role
metadata so a body line can never masquerade as discovery metadata.
"""

from __future__ import annotations

import ast
import pathlib
import re


FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:[ \t]*(.*))$")
FOLDED_MARKERS = {">", ">-", ">+", "|", "|-", "|+"}


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
        return parsed if isinstance(parsed, str) else value
    return value


def parse_simple_mapping(text: str) -> dict[str, str]:
    """Parse top-level scalar/folded fields from a YAML mapping."""
    lines = text.splitlines()
    values: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        match = FIELD.match(line) if line and not line[0].isspace() else None
        if not match:
            index += 1
            continue
        key, raw = match.groups()
        if raw in FOLDED_MARKERS:
            continuation: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index] or lines[index][0].isspace()):
                continuation.append(lines[index].strip())
                index += 1
            separator = " " if raw.startswith(">") else "\n"
            values[key] = separator.join(part for part in continuation if part)
            continue
        values[key] = _scalar(raw)
        index += 1
    return values


def read_frontmatter(path: pathlib.Path) -> tuple[dict[str, str] | None, str | None]:
    """Read only the leading `---` YAML block from a Markdown file."""
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return None, "missing leading YAML frontmatter"
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, "unterminated YAML frontmatter"
    return parse_simple_mapping("\n".join(lines[1:end])), None


def parse_inline_list(value: str) -> list[str]:
    """Parse Crew's schema-v2 inline list form (`[one, two]`)."""
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    return [_scalar(item.strip()) for item in value[1:-1].split(",") if item.strip()]
