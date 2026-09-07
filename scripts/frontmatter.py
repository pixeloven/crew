#!/usr/bin/env python3
"""Dependency-free parsing of the top-level fields Crew validators consume.

Harness-native validators remain responsible for full YAML conformance. These
helpers deliberately parse only the leading frontmatter block and simple role
metadata so a body line can never masquerade as discovery metadata.
"""

from __future__ import annotations

import pathlib
import re
from typing import Any


FIELD = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:[ \t]*(.*))$")
FOLDED_MARKERS = {">", ">-", ">+", "|", "|-", "|+"}
INTEGER = re.compile(r"^[+-]?(?:0|[1-9][0-9_]*|0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+)$")
FLOAT = re.compile(
    r"^[+-]?(?:(?:[0-9][0-9_]*)?\.[0-9_]+|[0-9][0-9_]*(?:\.[0-9_]*)?[eE][+-]?[0-9]+|\.inf|\.nan)$",
    re.IGNORECASE,
)
TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}(?:(?:[Tt]|[ \t]+)[0-9]{1,2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]*)?(?:[ \t]*(?:Z|[-+][0-9]{1,2}(?::[0-9]{2})?))?)?$"
)
SEXAGESIMAL = re.compile(r"^[+-]?[0-9][0-9_]*(?::[0-5]?[0-9])+$")


class ScalarParseError(ValueError):
    """Raised when a supported scalar contains invalid YAML syntax."""


def _double_quoted(value: str) -> str:
    escapes = {
        "0": "\0",
        "a": "\a",
        "b": "\b",
        "t": "\t",
        "n": "\n",
        "v": "\v",
        "f": "\f",
        "r": "\r",
        "e": "\x1b",
        " ": " ",
        '"': '"',
        "/": "/",
        "\\": "\\",
        "N": "\x85",
        "_": "\xa0",
        "L": "\u2028",
        "P": "\u2029",
    }
    result: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            result.append(character)
            index += 1
            continue
        index += 1
        if index >= len(value):
            raise ScalarParseError("unterminated escape in double-quoted scalar")
        escape = value[index]
        if escape in escapes:
            result.append(escapes[escape])
            index += 1
            continue
        widths = {"x": 2, "u": 4, "U": 8}
        if escape not in widths:
            raise ScalarParseError(f"unknown escape \\{escape} in double-quoted scalar")
        width = widths[escape]
        digits = value[index + 1:index + 1 + width]
        if len(digits) != width or not re.fullmatch(r"[0-9a-fA-F]+", digits):
            raise ScalarParseError(f"invalid \\{escape} escape in double-quoted scalar")
        codepoint = int(digits, 16)
        if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
            raise ScalarParseError(f"invalid Unicode scalar in \\{escape} escape")
        result.append(chr(codepoint))
        index += width + 1
    return "".join(result)


def _scalar(value: str) -> Any:
    value = value.strip()
    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if quote == '"' and character == "\\" and not escaped:
            escaped = True
            continue
        if character in {"'", '"'} and not escaped:
            if quote is None:
                quote = character
            elif quote == character:
                if quote == "'" and index + 1 < len(value) and value[index + 1] == "'":
                    escaped = True
                    continue
                quote = None
        if character == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            value = value[:index].rstrip()
            break
        escaped = False
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise ScalarParseError("unterminated single-quoted scalar")
        return value[1:-1].replace("''", "'")
    if value.startswith('"'):
        if len(value) < 2 or not value.endswith('"'):
            raise ScalarParseError("unterminated double-quoted scalar")
        return _double_quoted(value[1:-1])
    if value.startswith("[") and value.endswith("]"):
        return [_scalar(item.strip()) for item in value[1:-1].split(",") if item.strip()]
    if value.startswith("{") and value.endswith("}"):
        return {}
    if value.lower() in {"null", "~"}:
        return None
    if value.lower() in {"true", "false", "yes", "no", "on", "off"}:
        return value.lower() in {"true", "yes", "on"}
    if (
        INTEGER.fullmatch(value)
        or FLOAT.fullmatch(value)
        or SEXAGESIMAL.fullmatch(value)
        or re.fullmatch(r"[+-]?0[0-7_]+", value)
        or TIMESTAMP.fullmatch(value)
    ):
        return 0
    if value.startswith(("!", "&", "*")):
        return None
    return value


def parse_simple_mapping(text: str) -> dict[str, Any]:
    """Parse top-level scalar/folded fields from a YAML mapping."""
    lines = text.splitlines()
    values: dict[str, Any] = {}
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
        if not raw:
            sequence: list[Any] = []
            cursor = index + 1
            while cursor < len(lines) and (not lines[cursor] or lines[cursor][0].isspace()):
                stripped = lines[cursor].strip()
                if stripped:
                    if not stripped.startswith("- "):
                        sequence = []
                        break
                    sequence.append(_scalar(stripped[2:]))
                cursor += 1
            if sequence:
                values[key] = sequence
                index = cursor
                continue
        values[key] = _scalar(raw)
        index += 1
    return values


def read_frontmatter(path: pathlib.Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read only the leading `---` YAML block from a Markdown file."""
    lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        return None, "missing leading YAML frontmatter"
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, "unterminated YAML frontmatter"
    try:
        return parse_simple_mapping("\n".join(lines[1:end])), None
    except ScalarParseError as error:
        return None, f"invalid YAML frontmatter: {error}"


def parse_inline_list(value: str) -> list[str]:
    """Parse Crew's schema-v2 inline list form (`[one, two]`)."""
    parsed = _scalar(value)
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]
