---
name: python-conventions
description: Python conventions — stack, tooling, uv-workspace project structure, and patterns for CLI (Typer), MCP servers (FastMCP), Pydantic AI, testing (pytest), and packaging (uv). Load for any Python work.
tier: subject
requires: []
audience: [crew]
---

## Runtime and tooling

- **Python 3.12+** — minimum version across all Python packages
- **`uv`** — package manager and virtualenv management (`uv run`, `uv add`, `uv sync`)
- **`ruff`** — linting and formatting (replaces flake8, isort, black)
- **`pytest`** — test runner

## Project structure

Example uv-workspace layout (e.g. Harmony splits into `harmony-core` / `harmony-cli` / `harmony-mcp`). Names vary per project; the shape — one shared core library, thin surface packages depending on it — is the convention:

```
src/
├── <project>-core/   # Shared library: config, console, errors, plugins
├── <project>-cli/    # CLI (Typer + Rich) — depends on <project>-core
└── <project>-mcp/    # MCP servers (FastMCP) — one subpackage per server
```

## CLI (Typer + Rich)

If the project ships a CLI (e.g. Harmony's `hmy`), it is built with Typer. New commands follow the existing command-group pattern:

```python
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

@app.command()
def my_command(arg: str = typer.Argument(..., help="Description")):
    """One-line docstring shown in --help."""
    console.print(f"[green]{arg}[/green]")
```

CLI is the operator-facing surface. MCP tools are the agent-facing surface. Don't duplicate logic — if both surfaces need a capability, the MCP tool is canonical and the CLI is a thin wrapper.

## MCP servers (FastMCP)

MCP servers use FastMCP:

```python
from fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
def my_tool(param: str) -> str:
    """Tool description shown to agents."""
    return result
```

Tool descriptions must be precise — agents use them for tool selection. Phrasing matters.

## Pydantic AI

Agent orchestration uses Pydantic AI (`AnthropicModel` or `OpenAIModel` via LiteLLM passthrough). Structured output via Pydantic models. Exit codes: 0 success, 75 transient, 1 structural.

```python
from pydantic_ai import Agent
from pydantic import BaseModel

class AgentResult(BaseModel):
    summary: str
    status: str

agent = Agent(model, result_type=AgentResult)
```

## Testing

```bash
uv run pytest                  # Run all tests
uv run pytest tests/unit/      # Unit tests only
uv run pytest -x               # Stop on first failure
```

Tests live alongside source under `tests/`. Use real dependencies where possible — mocks that diverge from reality hide real failures.

## Linting and formatting

```bash
uv run ruff check              # Lint
uv run ruff check --fix        # Auto-fix
uv run ruff format             # Format
```

Ruff config lives in `pyproject.toml`. Run before every PR — CI will enforce it.

## Running the CLI

```bash
uv run <cli> <command>         # Always via uv run, never the bare entrypoint
```

The CLI entrypoint is defined in the CLI package's `pyproject.toml`. The venv is managed by `uv`; never activate it manually.

## Development setup

If the project's CLI ships dev-workflow commands, prefer them over raw tool invocations — they wrap uv/ruff plus any repo-specific linters. Example shape (e.g. Harmony's `hmy dev`):

```bash
<cli> dev setup                # Creates .venv, installs linters + extra collections
<cli> dev lint                 # ruff + repo-specific linters (e.g. yamllint, ansible-lint)
<cli> dev fmt                  # Auto-format (ruff, plus e.g. terraform fmt)
```

Without such a wrapper, use the `uv run ruff` / `uv run pytest` commands above directly.
