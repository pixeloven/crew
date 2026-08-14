---
name: mcp-server-design
description: Designing and implementing MCP servers with FastMCP — tool design, description quality, structured error handling, failure semantics, registration, and the MCP vs CLI surface decision. Load when building new MCP tools or servers.
tier: subject
requires: []
audience: [crew]
---

## Surface decision first

Before writing an MCP tool, confirm the primary caller: agent, human, or both. The full MCP-vs-CLI decision table — and the off-the-shelf-first default that precedes it — lives in `agent-platform-design`; apply it before writing any server code.

The FastMCP-specific consequences:
- When MCP is the canonical surface, the MCP tool owns validation, schema, and side effects. Any CLI shim forwards structured args and translates exit codes — it never duplicates logic; it calls the MCP tool or the underlying library directly.
- Human-primary capabilities belong in the project's CLI; don't add an MCP tool unless agents genuinely need it.

## FastMCP basics

```python
from fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
def my_tool(param: str, optional_param: int = 10) -> dict:
    """
    One concise sentence: what this tool does and what it returns.
    Agents use this description for tool selection — precision matters.
    """
    return {"result": ..., "status": "success"}
```

## Tool description quality

The tool docstring is the primary mechanism agents use to decide whether to call the tool. Write it as:
- One sentence describing the action and output
- If the tool has important constraints or side effects, add them in a second sentence

Bad: `"""Search the vault."""`
Good: `"""Full-text search across all Obsidian vault content. Returns matching note paths and excerpts."""`

## Error handling

Return structured errors rather than raising exceptions — exceptions surface as tool call failures with no useful context:

```python
@mcp.tool()
def my_tool(path: str) -> dict:
    """Read a note from the vault by path."""
    try:
        content = vault.read(path)
        return {"content": content, "found": True}
    except NoteNotFoundError:
        return {"content": None, "found": False, "error": f"No note at {path}"}
```

For transient errors (network, rate limits), raise — let the caller decide on retry. For logical errors (not found, invalid input), return structured error so the agent can handle it.

## Failure semantics by surface

The same underlying capability may have different failure modes across surfaces:

| Surface | Failure mode | Why |
|---|---|---|
| MCP tool (agent side effect) | Soft-fail — log, return error, don't block | Vault trouble shouldn't abort an unrelated task |
| CLI command (human primary action) | Hard-fail — exit 1, print error | Operator needs to know their action didn't land |

Document this asymmetry if both surfaces exist.

## Server registration

MCP servers are registered per the harness's MCP config (`.mcp.json` for Claude Code, the pi MCP config for pi.dev), or federated behind the platform's LiteLLM gateway so any client whose virtual key holds the right access group can reach them — see `litellm-routing-model`.

## Writing to the substrate from an MCP server

If your MCP server emits structured knowledge (research outputs, runbooks, decisions, world facts) it should write into the platform's memory substrate rather than its own private store. See `memory-substrate` — the substrate owns layer selection, tool routing, and the write contract.
