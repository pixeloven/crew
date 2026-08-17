---
name: mcp-server-design
description: Designing and implementing MCP servers with FastMCP — tool design, description quality, structured error handling, failure semantics, registration, and the three-class surface decision (MCP vs AXI vs CLI). Load when building new MCP tools or servers.
tier: subject
requires: []
---

## Surface decision first

Before writing an MCP tool, confirm the primary caller *and* whose credentials the capability carries. The full three-class decision table — MCP (federated, authorization-carrying) vs AXI (local agent tooling, no auth of its own) vs CLI (humans, scripts, CI) — and the off-the-shelf-first default that precedes it both live in `agent-platform-design`; apply it before writing any server code. A capability whose credential must never leave one machine belongs in an AXI, however convenient federating it would be.

The FastMCP-specific consequences:
- When MCP is the canonical surface, the MCP tool owns validation, schema, and side effects. Any CLI shim forwards structured args and translates exit codes — it never duplicates logic; it calls the MCP tool or the underlying library directly.
- Human-primary capabilities belong in the project's CLI; add an MCP tool when an agent is a caller.

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

MCP servers are registered per the harness's MCP config (`.mcp.json` for Claude Code, the pi MCP config for pi.dev), or federated behind the platform's LiteLLM gateway so any client whose virtual key holds the right access group can reach them — see the project's gateway-routing local skill.

## Writing to the substrate from an MCP server

If your MCP server emits structured knowledge (research outputs, runbooks, decisions, world facts) it should write into the platform's memory substrate rather than its own private store. See the project's knowledge-capture local skill — the substrate owns layer selection, tool routing, and the write contract.

## Tool descriptions are the selection surface

A tool's description is how a model decides whether to call it. Treat it as the interface, not documentation — a correct tool with an unfindable description is an unused tool.

1. **Open with an imperative one-liner** — what the tool *does*, in a sentence the model can match a task against.
2. **Say when to use it**, and when to reach for something else. Selection is comparative; a description that only describes itself gives the model nothing to choose on.
3. **Don't dump the docstring.** Parameter detail belongs in the schema, which the model reads separately. Prose repeating the schema costs context and buries the trigger.
4. **Avoid circular definitions.** "Runs the sync operation" tells a model nothing it couldn't guess from the name.
5. **Cover the vocabulary a caller would use** — verbs and aliases the model might reach for, not only your internal noun. A search tool that never says "find" or "look up" loses to one that does.
6. **Disambiguate near-neighbours explicitly.** If two tools could plausibly serve the same request, each description should say what distinguishes it.
7. **Front-load.** Long descriptions get truncated or skimmed; the discriminating clause goes first.

**Recall smoke-test for a new server.** Before shipping, write down five tasks a caller would plausibly bring, then check — without looking at the tool list — which tool each description would attract. Anything that attracts nothing needs a rewrite; anything that attracts everything is too vague to select against. This catches the failure that a schema review never will: a tool that is correct, documented, and never chosen.

The same principle governs skill descriptions — see the description guidance in `agent-platform-design`.
