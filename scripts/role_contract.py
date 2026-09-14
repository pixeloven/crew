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

# Claude expresses the contract as a denylist; pi expresses it as an allowlist.
# `drafts` deliberately retains Write: on Claude it can create AND overwrite a
# file, while Edit/NotebookEdit (surgical modification) remain denied.
WRITE_POSTURES = {
    "none": {
        "claude": {"denied": ["Write", "Edit", "NotebookEdit"]},
        "pi": {"allowed": ["read", "bash", "grep", "find"]},
    },
    "drafts": {
        "claude": {"denied": ["Edit", "NotebookEdit"]},
        "pi": {"allowed": ["read", "write", "bash", "grep", "find"]},
    },
    "full": {
        "claude": {"denied": []},
        "pi": {"allowed": ["read", "write", "edit", "bash", "grep", "find"]},
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
    if harness == "claude":
        denied = list(raw["denied"])
        allowed = []
        if writes == "none":
            effect = "dedicated file-write tools are denied"
        elif writes == "drafts":
            effect = "Write may create and overwrite files; surgical Edit tools are denied"
        else:
            effect = "dedicated file-write tools are unrestricted"
    else:
        denied = []
        allowed = list(raw["allowed"])
        if writes == "none":
            effect = "dedicated write and edit tools are absent"
        elif writes == "drafts":
            effect = "write may create and overwrite files; surgical edit is absent"
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
