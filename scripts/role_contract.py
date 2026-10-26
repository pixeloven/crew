#!/usr/bin/env python3
"""Shared role frontmatter and effective-write-posture contract.

The renderer and consumer validator import this module so the generated
frontmatter, Doctor output, and comments cannot acquire different meanings.
"""

import re


CLAUDE_ROLE_NAME = re.compile(r"^[a-z]+(?:-[a-z]+)*$")

FORBIDDEN_RUNTIME_KEYS = {
    "model": "the dispatcher's choice — both harnesses inherit the session model",
    "thinking": "reasoning depth is the dispatcher's choice",
    "effort": "reasoning depth is the dispatcher's choice",
    "model_reasoning_effort": "reasoning depth is the dispatcher's choice",
    "turnBudget": "blast radius is the dispatcher's choice",
    "maxTurns": "blast radius is the dispatcher's choice",
}

# pi-subagents namespaces a package agent as `<package>.<name>`. Crew's rendered
# pi roles declare `package: crew`, so they register as `crew.<role>` and never
# replace pi-subagents' built-in `reviewer`/`researcher`. Same identity as the
# plugin name (`PLUGIN_NAME` in crew_doctor.py) — one PixelOven identity.
PI_PACKAGE_NAME = "crew"

# Both harnesses express the contract as a SUBTRACTION from the default tool set,
# so `writes:` means one thing everywhere: which dedicated file-write tools are
# removed. pi uses `excludeTools` (honoured by pi-subagents >=0.62.0),
# not a `tools:` allowlist: pi's `tools:` is strict and also shuts out ambient
# extensions (the MCP adapter) in background runs. MCP side effects are governed
# by behaviour, not by this posture, on every harness.
# `drafts` deliberately retains Write/write: it can create AND overwrite a file,
# while surgical Edit (and Claude's NotebookEdit) remain denied.
WRITE_POSTURES = {
    "none": {
        "claude": {"denied": ["Write", "Edit", "NotebookEdit"]},
        "pi": {"denied": ["write", "edit"]},
    },
    "drafts": {
        "claude": {"denied": ["Edit", "NotebookEdit"]},
        "pi": {"denied": ["edit"]},
    },
    "full": {
        "claude": {"denied": []},
        "pi": {"denied": []},
    },
}


def claude_role_identity(value: object) -> str | None:
    """Return a normalized Claude role identity when its syntax is supported."""
    if not isinstance(value, str):
        return None
    identity = value.strip()
    return identity if CLAUDE_ROLE_NAME.fullmatch(identity) else None


def effective_posture(writes: str, harness: str) -> dict[str, object]:
    """Return the effective, reportable posture for one rendered role."""
    if writes not in WRITE_POSTURES:
        raise ValueError(f"unknown writes posture: {writes}")
    if harness not in {"claude", "pi"}:
        raise ValueError(f"unknown harness: {harness}")

    raw = WRITE_POSTURES[writes][harness]
    denied = list(raw["denied"])
    allowed: list[str] = []
    if harness == "claude":
        if writes == "none":
            effect = "dedicated file-write tools are denied"
        elif writes == "drafts":
            effect = "Write may create and overwrite files; surgical Edit tools are denied"
        else:
            effect = "dedicated file-write tools are unrestricted"
    else:
        if writes == "none":
            effect = "write and edit are excluded from the default tool set"
        elif writes == "drafts":
            effect = "write may create and overwrite files; surgical edit is excluded"
        else:
            effect = "write and edit tools are available"

    return {
        "writes": writes,
        "harness": harness,
        "allowed_tools": allowed,
        "denied_tools": denied,
        "write_effect": effect,
        "caveat": "shell access makes the frontmatter posture advisory unless the host sandbox enforces it",
    }
