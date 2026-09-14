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
BLOCK_SCALAR_HEADER = re.compile(
    r"^([|>])(?:(?:([1-9])([+-])?)|(?:([+-])([1-9])?))?"
    r"(?:[ \t]+#.*)?[ \t]*$"
)
OPAQUE_NESTED_FIELDS = {"hooks", "mcpServers"}
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


def _block_scalar_header(value: str) -> tuple[str, int | None] | None:
    match = BLOCK_SCALAR_HEADER.fullmatch(value)
    if match is None:
        return None
    indentation = match.group(2) or match.group(5)
    return match.group(1), int(indentation) if indentation else None


def _over_indented_leading_blank(
    leading_blank_lines: list[tuple[int, int]],
    content_indentation: int,
) -> int | None:
    return next(
        (
            line_number
            for indentation, line_number in leading_blank_lines
            if indentation > content_indentation
        ),
        None,
    )


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


def _flow_entries(content: str, allow_nested_flow: bool) -> list[str]:
    entries: list[str] = []
    quote: str | None = None
    closers: list[str] = []
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
            quote = character
        elif character in "[{":
            if not allow_nested_flow:
                raise ScalarParseError("nested flow collections are unsupported")
            closers.append("]" if character == "[" else "}")
        elif character in "]}":
            if not closers or character != closers.pop():
                raise ScalarParseError("mismatched flow-collection delimiter")
        elif character == "," and not closers:
            entry = content[start:index].strip()
            if not entry:
                raise ScalarParseError("empty flow-collection entry")
            entries.append(entry)
            start = index + 1
        elif character == "#" and (index == 0 or content[index - 1].isspace()):
            raise ScalarParseError("comments in flow collections are unsupported")
        index += 1
    if quote is not None:
        raise ScalarParseError("unterminated quote in flow collection")
    if closers:
        raise ScalarParseError("unterminated nested flow collection")
    final = content[start:].strip()
    if final:
        entries.append(final)
    return entries


def _flow_mapping_separator(entry: str) -> int | None:
    quote: str | None = None
    closers: list[str] = []
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
        elif character in {"'", '"'}:
            quote = character
        elif character in "[{":
            closers.append("]" if character == "[" else "}")
        elif character in "]}":
            if not closers or character != closers.pop():
                raise ScalarParseError("mismatched flow-collection delimiter")
        elif character == ":" and not closers:
            return index
        index += 1
    return None


def _flow_sequence(value: str, allow_nested_flow: bool = False) -> list[Any]:
    if not value.endswith("]"):
        raise ScalarParseError("unterminated flow sequence")
    entries = _flow_entries(value[1:-1], allow_nested_flow)
    return [
        _scalar(entry, allow_nested_flow=allow_nested_flow)
        for entry in entries
    ]


def _flow_mapping(value: str, allow_nested_flow: bool = False) -> dict[str, Any]:
    if not value.endswith("}"):
        raise ScalarParseError("unterminated flow mapping")
    entries = _flow_entries(value[1:-1], allow_nested_flow)

    result: dict[str, Any] = {}
    for entry in entries:
        separator_index = _flow_mapping_separator(entry)
        if separator_index is None:
            raise ScalarParseError("invalid flow-mapping entry")
        key_text = entry[:separator_index].strip()
        value_text = entry[separator_index + 1:].strip()
        if not key_text or not value_text and not allow_nested_flow:
            raise ScalarParseError("invalid flow-mapping entry")
        key = _scalar(key_text.strip())
        if not isinstance(key, str) or not key:
            raise ScalarParseError("flow-mapping keys must be strings")
        if key in result:
            raise ScalarParseError(f"duplicate flow-mapping key {key!r}")
        result[key] = _scalar(
            value_text.strip(),
            allow_nested_flow=allow_nested_flow,
        )
    return result


def _scalar(value: str, *, allow_nested_flow: bool = False) -> Any:
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
        return _flow_sequence(value, allow_nested_flow)
    if value.startswith("{"):
        return _flow_mapping(value, allow_nested_flow)
    if value[0] in "]}":
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


def _nested_mapping_field(value: str) -> tuple[str, str] | None:
    value = _without_comment(value).rstrip()
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
        elif character in {"'", '"'} and not value[:index].strip():
            quote = character
        elif character == ":" and (
            index + 1 == len(value) or value[index + 1].isspace()
        ):
            key_text = value[:index].strip()
            if not key_text:
                raise ScalarParseError("empty mapping key")
            key = _scalar(key_text)
            if not isinstance(key, str) or not key:
                raise ScalarParseError("mapping keys must be strings")
            return key, value[index + 1 :].lstrip(" \t")
        index += 1
    return None


def _validate_nested_mapping(lines: list[str], line_offset: int) -> None:
    tokens: list[tuple[int, str, int]] = []
    for offset, line in enumerate(lines):
        if not line.strip():
            if line:
                prefix = line[: len(line) - len(line.lstrip(" "))]
                tokens.append((len(prefix), line[len(prefix) :], line_offset + offset))
            continue
        prefix = line[: len(line) - len(line.lstrip(" "))]
        tokens.append((len(prefix), line[len(prefix) :], line_offset + offset))
    if not tokens:
        return

    def scalar(raw: str, line_number: int) -> None:
        try:
            _scalar(raw, allow_nested_flow=True)
        except ScalarParseError as error:
            raise ScalarParseError(f"{error} on line {line_number}") from error

    def skip_comments(position: int) -> int:
        while position < len(tokens) and (
            not tokens[position][1].strip() or tokens[position][1].startswith("#")
        ):
            position += 1
        return position

    def block_scalar(
        position: int,
        parent_indentation: int,
        declared_indentation: int | None,
    ) -> int:
        content_indentation = (
            parent_indentation + declared_indentation
            if declared_indentation is not None
            else None
        )
        saw_content = False
        leading_blank_lines: list[tuple[int, int]] = []
        while position < len(tokens) and (
            not tokens[position][1].strip()
            or tokens[position][0] > parent_indentation
        ):
            current, text, line_number = tokens[position]
            if not text.strip():
                if not saw_content:
                    leading_blank_lines.append((current, line_number))
                position += 1
                continue
            if content_indentation is None:
                content_indentation = current
                over_indented = _over_indented_leading_blank(
                    leading_blank_lines,
                    content_indentation,
                )
                if over_indented is not None:
                    raise ScalarParseError(
                        f"invalid block indentation on line {over_indented}"
                    )
            elif current < content_indentation:
                if saw_content and text.startswith("#"):
                    return position
                raise ScalarParseError(
                    f"invalid block indentation on line {line_number}"
                )
            elif not saw_content:
                over_indented = _over_indented_leading_blank(
                    leading_blank_lines,
                    content_indentation,
                )
                if over_indented is not None:
                    raise ScalarParseError(
                        f"invalid block indentation on line {over_indented}"
                    )
            saw_content = True
            position += 1
        return position

    def mapping(
        position: int,
        indentation: int,
        initial_keys: set[str] | None = None,
    ) -> int:
        keys = set(initial_keys or ())
        while position < len(tokens):
            position = skip_comments(position)
            if position >= len(tokens):
                return position
            current, text, line_number = tokens[position]
            if text.startswith("\t"):
                raise ScalarParseError(f"tab indentation on line {line_number}")
            if current < indentation:
                return position
            if current > indentation:
                raise ScalarParseError(f"unexpected indentation on line {line_number}")
            if text == "-" or text.startswith("- "):
                raise ScalarParseError(f"mixed mapping and sequence on line {line_number}")
            try:
                field = _nested_mapping_field(text)
            except ScalarParseError as error:
                raise ScalarParseError(f"{error} on line {line_number}") from error
            if field is None:
                raise ScalarParseError(f"invalid mapping entry on line {line_number}")
            key, raw = field
            if key in keys:
                raise ScalarParseError(f"duplicate mapping key {key!r}")
            keys.add(key)
            position += 1
            header = _block_scalar_header(raw)
            content = _without_comment(raw).rstrip()
            if header is not None:
                position = block_scalar(position, indentation, header[1])
            elif content:
                scalar(raw, line_number)
            else:
                position = skip_comments(position)
                if position < len(tokens) and tokens[position][0] > indentation:
                    position = node(position, tokens[position][0])
        return position

    def sequence(position: int, indentation: int) -> int:
        while position < len(tokens):
            position = skip_comments(position)
            if position >= len(tokens):
                return position
            current, text, line_number = tokens[position]
            if text.startswith("\t"):
                raise ScalarParseError(f"tab indentation on line {line_number}")
            if current < indentation:
                return position
            if current > indentation:
                raise ScalarParseError(f"unexpected indentation on line {line_number}")
            if text != "-" and not text.startswith("- "):
                raise ScalarParseError(f"mixed sequence and mapping on line {line_number}")
            item_text = text[1:]
            separation = len(item_text) - len(item_text.lstrip(" "))
            raw_item = item_text.strip()
            position += 1
            if not _without_comment(raw_item).rstrip():
                position = skip_comments(position)
                if position < len(tokens) and tokens[position][0] > indentation:
                    position = node(position, tokens[position][0])
                continue
            try:
                field = _nested_mapping_field(raw_item)
            except ScalarParseError as error:
                raise ScalarParseError(f"{error} on line {line_number}") from error
            if field is None:
                scalar(raw_item, line_number)
                if position < len(tokens) and tokens[position][0] > indentation:
                    raise ScalarParseError(
                        f"unexpected indentation on line {tokens[position][2]}"
                    )
                continue
            key, raw = field
            item_indentation = indentation + 1 + separation
            header = _block_scalar_header(raw)
            content = _without_comment(raw).rstrip()
            if header is not None:
                position = block_scalar(position, item_indentation, header[1])
            elif content:
                scalar(raw, line_number)
            else:
                position = skip_comments(position)
                if position < len(tokens) and tokens[position][0] > item_indentation:
                    position = node(position, tokens[position][0])
            position = skip_comments(position)
            if position < len(tokens) and tokens[position][0] == item_indentation:
                position = mapping(position, item_indentation, {key})
            elif position < len(tokens) and tokens[position][0] > indentation:
                raise ScalarParseError(
                    f"unexpected indentation on line {tokens[position][2]}"
                )
        return position

    def node(position: int, indentation: int) -> int:
        text = tokens[position][1]
        if text == "-" or text.startswith("- "):
            return sequence(position, indentation)
        return mapping(position, indentation)

    position = skip_comments(0)
    if position == len(tokens):
        return
    position = node(position, tokens[position][0])
    if position != len(tokens):
        raise ScalarParseError(f"invalid nested mapping on line {tokens[position][2]}")


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
        header = _block_scalar_header(raw)
        content = _without_comment(raw).rstrip()
        if header is not None:
            continuation: list[str] = []
            indentation = header[1]
            leading_blank_lines: list[tuple[int, int]] = []
            saw_content = False
            index += 1
            while index < len(lines) and (not lines[index] or lines[index][0].isspace()):
                if lines[index].startswith("\t"):
                    raise ScalarParseError(f"tab indentation on line {index + 1}")
                current = len(lines[index]) - len(lines[index].lstrip(" "))
                if not lines[index].strip():
                    if lines[index] and not saw_content:
                        leading_blank_lines.append((current, index + 1))
                    continuation.append(lines[index].strip())
                    index += 1
                    continue
                if indentation is None:
                    indentation = current
                elif current < indentation:
                    raise ScalarParseError(f"invalid block indentation on line {index + 1}")
                if not saw_content:
                    over_indented = _over_indented_leading_blank(
                        leading_blank_lines,
                        indentation,
                    )
                    if over_indented is not None:
                        raise ScalarParseError(
                            f"invalid block indentation on line {over_indented}"
                        )
                saw_content = True
                continuation.append(lines[index].strip())
                index += 1
            separator = " " if header[0] == ">" else "\n"
            values[key] = separator.join(part for part in continuation if part)
            continue
        if not content:
            if key in OPAQUE_NESTED_FIELDS:
                continuation: list[str] = []
                cursor = index + 1
                while cursor < len(lines) and (
                    not lines[cursor] or lines[cursor][0].isspace()
                ):
                    if lines[cursor].startswith("\t"):
                        raise ScalarParseError(f"tab indentation on line {cursor + 1}")
                    continuation.append(lines[cursor])
                    cursor += 1
                if any(line.strip() and not line.lstrip().startswith("#") for line in continuation):
                    _validate_nested_mapping(continuation, index + 2)
                    values[key] = "\n".join(continuation)
                    index = cursor
                    continue
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
        values[key] = _scalar(
            raw,
            allow_nested_flow=key in OPAQUE_NESTED_FIELDS,
        )
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
