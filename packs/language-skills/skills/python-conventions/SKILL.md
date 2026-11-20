---
name: python-conventions
description: Use when doing any Python work — packages, CLIs, MCP servers, agents, tests. Covers the Python floor, uv workspaces and packaging, Ruff and pytest gates, and one-core-many-surfaces layout; house frameworks come from the project's python-stack slot.
tier: subject
requires: [plugin:crew@>=0.46.0]
expects-local: [python-stack, agent-runtime]
---

Where the project has a `python-stack` local skill, its choices (version floor,
frameworks, layout, commands) outrank anything below; what follows is the portable
default for a project that has not chosen. Framework names below are examples of a
choice, not the choice.

## Runtime and tooling

- **One Python floor** — set `requires-python` in every package's `pyproject.toml`
  to the same minimum. Default: **3.12+**.
- **`uv`** — package manager and virtualenv management (`uv run`, `uv add`, `uv sync`).
  Commit `uv.lock`.
- **`ruff`** — linting and formatting (replaces flake8, isort, black).
- **`pytest`** — test runner.

## Project structure

Prefer a uv workspace: one shared core library, thin surface packages that depend on
it. Names vary per project; the shape is the convention:

```
src/
├── <project>-core/   # Shared library: config, console, errors, plugins
├── <project>-cli/    # Operator-facing CLI — depends on <project>-core
└── <project>-mcp/    # Agent-facing MCP servers — one subpackage per server
```

Logic lives in the core. A surface parses input, calls the core, and renders output.

## Surfaces: CLI and MCP

The CLI is the operator-facing surface; MCP tools are the agent-facing surface. Don't
duplicate logic — if both need a capability, the MCP tool is canonical and the CLI is a
thin wrapper over the same core call.

- **New commands follow the existing command-group pattern.** Read a sibling command
  before adding one; match its argument style, help text and output.
- **Docstrings are interface.** A CLI command's docstring is its `--help`; an MCP
  tool's description is how agents select it. Phrase both precisely.
- **Use the project's console, not `print`.** Route output through one console object
  so styling, quiet modes and stderr handling stay in one place.

Example of the shape, with Typer and Rich as the CLI choice:

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

And with FastMCP as the MCP choice:

```python
from fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
def my_tool(param: str) -> str:
    """Tool description shown to agents."""
    return core_function(param)
```

## Agents and structured output

When Python code calls a model, validate its output into a typed model (Pydantic or
the framework's equivalent) rather than parsing free text, and map outcomes to the
project's exit-code contract (the `agent-runtime` local skill, if it defines one).

Which agent framework, which model class, and whether it points at a provider directly
or at a gateway are the project's call, not this skill's. A convention skill that names
a vendor picks the project's provider for it. Example of the shape, with Pydantic AI:

```python
from pydantic import BaseModel
from pydantic_ai import Agent

class AgentResult(BaseModel):
    summary: str
    status: str

agent = Agent(model, output_type=AgentResult)  # model comes from the project's routing
```

## Testing

```bash
uv run pytest                  # Run all tests
uv run pytest tests/unit/      # Unit tests only
uv run pytest -x               # Stop on first failure
```

Tests live in each package's `tests/`. Use real dependencies where possible — mocks
that diverge from reality hide real failures.

## Linting and formatting

```bash
uv run ruff check              # Lint
uv run ruff check --fix        # Auto-fix
uv run ruff format             # Format
```

Ruff config lives in `pyproject.toml`. Run before every PR; CI should enforce it.

## Running entrypoints

```bash
uv run <cli> <command>         # Always via uv run, never the bare entrypoint
```

Entrypoints are declared in each package's `pyproject.toml`. The venv is managed by
`uv`; never activate it manually.

If the project's CLI ships dev-workflow commands (for example `<cli> dev lint` wrapping
Ruff plus repo-specific linters), prefer them over raw tool invocations. Without such a
wrapper, use the `uv run ruff` / `uv run pytest` commands above directly.
