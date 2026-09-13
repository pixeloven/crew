#!/usr/bin/env python3
"""Dependency-free validation of the YAML subset Crew metadata consumes.

These helpers accept only a strict top-level mapping with scalar, folded, and
scalar-sequence values, so unsupported or malformed YAML cannot be mistaken for
valid discovery metadata.
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
        if character == '"':
            raise ScalarParseError("unescaped quote in double-quoted scalar")
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


def _without_comment(value: str) -> str:
    quote: str | None = None
    index = 0
    while index < len(value):
        character = value[index]
        if quote == "'":
            if character == "'":
                if index + 1 < len(value) and value[index + 1] == "'":
                    index += 2
                    continue
                quote = None
        elif quote == '"':
            if character == "\\":
                index += 2
                continue
            if character == '"':
                quote = None
        elif character in {"'", '"'} and index == 0:
            quote = character
        elif character == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
        index += 1
    if quote is not None:
        raise ScalarParseError("unterminated quoted scalar")
    return value.rstrip()


def _flow_sequence(value: str) -> list[Any]:
    if not value.endswith("]"):
        raise ScalarParseError("unterminated flow sequence")
    content = value[1:-1]
    items: list[str] = []
    quote: str | None = None
    start = 0
    index = 0
    while index < len(content):
        character = content[index]
        if quote == "'":
            if character == "'":
                if index + 1 < len(content) and content[index + 1] == "'":
                    index += 2
                    continue
                quote = None
        elif quote == '"':
            if character == "\\":
                index += 2
                continue
            if character == '"':
                quote = None
        elif character in {"'", '"'} and not content[start:index].strip():
            quote = character
        elif character == ",":
            item = content[start:index].strip()
            if not item:
                raise ScalarParseError("empty flow-sequence entry")
            items.append(item)
            start = index + 1
        elif character == "#" and (index == 0 or content[index - 1].isspace()):
            raise ScalarParseError("comments in flow sequences are unsupported")
        elif character in "[]{}":
            raise ScalarParseError("nested flow collections are unsupported")
        index += 1
    if quote is not None:
        raise ScalarParseError("unterminated quote in flow sequence")
    final = content[start:].strip()
    if final:
        items.append(final)
    return [_scalar(item) for item in items]


def _flow_mapping(value: str) -> dict[str, Any]:
    if not value.endswith("}"):
        raise ScalarParseError("unterminated flow mapping")
    content = value[1:-1]
    entries: list[str] = []
    quote: str | None = None
    start = 0
    index = 0
    while index < len(content):
        character = content[index]
        if quote == "'":
            if character == "'":
                if index + 1 < len(content) and content[index + 1] == "'":
                    index += 2
                    continue
                quote = None
        elif quote == '"':
            if character == "\\":
                index += 2
                continue
            if character == '"':
                quote = None
        elif character in {"'", '"'}:
            prefix = content[start:index].rstrip()
            if not prefix or prefix.endswith(":"):
                quote = character
        elif character == ",":
            entry = content[start:index].strip()
            if not entry:
                raise ScalarParseError("empty flow-mapping entry")
            entries.append(entry)
            start = index + 1
        elif character == "#" and (index == 0 or content[index - 1].isspace()):
            raise ScalarParseError("comments in flow mappings are unsupported")
        elif character in "[]{}":
            raise ScalarParseError("nested flow collections are unsupported")
        index += 1
    if quote is not None:
        raise ScalarParseError("unterminated quote in flow mapping")
    final = content[start:].strip()
    if final:
        entries.append(final)
    elif content.rstrip().endswith(","):
        pass
    elif content.strip():
        raise ScalarParseError("empty flow-mapping entry")

    result: dict[str, Any] = {}
    for entry in entries:
        quote = None
        separator_index = None
        index = 0
        while index < len(entry):
            character = entry[index]
            if quote == "'":
                if character == "'":
                    if index + 1 < len(entry) and entry[index + 1] == "'":
                        index += 2
                        continue
                    quote = None
            elif quote == '"':
                if character == "\\":
                    index += 2
                    continue
                if character == '"':
                    quote = None
            elif character in {"'", '"'} and not entry[:index].strip():
                quote = character
            elif character == ":":
                separator_index = index
                break
            index += 1
        if separator_index is None:
            raise ScalarParseError("invalid flow-mapping entry")
        key_text = entry[:separator_index].strip()
        value_text = entry[separator_index + 1:].strip()
        if not key_text or not value_text:
            raise ScalarParseError("invalid flow-mapping entry")
        key = _scalar(key_text.strip())
        if not isinstance(key, str) or not key:
            raise ScalarParseError("flow-mapping keys must be strings")
        if key in result:
            raise ScalarParseError(f"duplicate flow-mapping key {key!r}")
        result[key] = _scalar(value_text.strip())
    return result


def _scalar(value: str) -> Any:
    value = _without_comment(value.strip())
    if not value:
        return None
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise ScalarParseError("unterminated single-quoted scalar")
        inner = value[1:-1]
        parsed: list[str] = []
        index = 0
        while index < len(inner):
            if inner[index] != "'":
                parsed.append(inner[index])
                index += 1
                continue
            if index + 1 >= len(inner) or inner[index + 1] != "'":
                raise ScalarParseError("unescaped quote in single-quoted scalar")
            parsed.append("'")
            index += 2
        return "".join(parsed)
    if value.startswith('"'):
        if len(value) < 2 or not value.endswith('"'):
            raise ScalarParseError("unterminated double-quoted scalar")
        return _double_quoted(value[1:-1])
    if value.startswith("["):
        return _flow_sequence(value)
    if value.startswith("{"):
        return _flow_mapping(value)
    if value[0] in "]}" or any(character in value for character in "[]{}"):
        raise ScalarParseError("unmatched flow-collection delimiter")
    if re.search(r":(?:[ \t]|$)", value):
        raise ScalarParseError("mapping separator in plain scalar")
    if (
        value in {"-", "?", ":"}
        or value[0] in {",", ">", "|"}
        or value.startswith(("- ", "? ", ": ", "%", "@", "`"))
    ):
        raise ScalarParseError("invalid plain-scalar indicator")
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
        raise ScalarParseError("tags, anchors, and aliases are unsupported")
    return value


def parse_simple_mapping(text: str) -> dict[str, Any]:
    """Parse top-level scalar/folded fields from a YAML mapping."""
    lines = text.splitlines()
    values: dict[str, Any] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("\t"):
            raise ScalarParseError(f"tab indentation on line {index + 1}")
        if line.lstrip().startswith("#"):
            index += 1
            continue
        if line[0].isspace():
            raise ScalarParseError(f"unexpected indentation on line {index + 1}")
        match = FIELD.fullmatch(line)
        if not match:
            raise ScalarParseError(f"invalid mapping entry on line {index + 1}")
        key, raw = match.groups()
        if key in values:
            raise ScalarParseError(f"duplicate mapping key {key!r}")
        if raw in FOLDED_MARKERS:
            continuation: list[str] = []
            indentation: int | None = None
            index += 1
            while index < len(lines) and (not lines[index] or lines[index][0].isspace()):
                if lines[index].startswith("\t"):
                    raise ScalarParseError(f"tab indentation on line {index + 1}")
                if lines[index].strip():
                    current = len(lines[index]) - len(lines[index].lstrip(" "))
                    if indentation is None:
                        indentation = current
                    elif current < indentation:
                        raise ScalarParseError(f"invalid block indentation on line {index + 1}")
                continuation.append(lines[index].strip())
                index += 1
            separator = " " if raw.startswith(">") else "\n"
            values[key] = separator.join(part for part in continuation if part)
            continue
        if not raw:
            sequence: list[Any] = []
            indentation: int | None = None
            cursor = index + 1
            while cursor < len(lines) and (not lines[cursor] or lines[cursor][0].isspace()):
                if lines[cursor].startswith("\t"):
                    raise ScalarParseError(f"tab indentation on line {cursor + 1}")
                stripped = lines[cursor].strip()
                if stripped and not stripped.startswith("#"):
                    current = len(lines[cursor]) - len(lines[cursor].lstrip(" "))
                    if indentation is None:
                        indentation = current
                    elif current != indentation:
                        raise ScalarParseError(f"inconsistent sequence indentation on line {cursor + 1}")
                    if stripped == "-":
                        sequence.append(None)
                    elif stripped.startswith("- "):
                        sequence.append(_scalar(stripped[2:]))
                    else:
                        raise ScalarParseError(f"invalid block sequence on line {cursor + 1}")
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
