---
name: <project>-python-stack
description: <Project>'s Python house choices — version floor, workspace layout, CLI, MCP and agent frameworks, console output, and dev commands. Load before writing or reviewing Python in this repo; it outranks language-skills' python-conventions defaults.
---

<!-- language-skills slot: python-stack. Read by python-conventions.
     Most of this is discoverable: with uv on PATH, crew's `learn` can draft these
     sections from `uv tree` and the pyproject.toml files as a proposal for the operator
     to promote. python-conventions runs on its stated defaults while a section is empty. -->

## Python floor and toolchain

<!-- crew:discoverable capability=cli:uv -->

> **▸ Fill:** the `requires-python` floor every package shares, and the package manager, linter, formatter and test runner if they differ from uv, Ruff and pytest.

## Workspace layout

<!-- crew:discoverable capability=cli:uv -->

> **▸ Fill:** the workspace members and what each is for (shared core, CLI, MCP servers, workers), and where tests live.

## Frameworks

<!-- crew:discoverable capability=cli:uv -->

> **▸ Fill:** the library chosen for each job and any it replaced — CLI (e.g. Typer, Click), MCP servers (e.g. FastMCP, the official SDK), agents and structured output (e.g. Pydantic AI), console output (e.g. Rich instead of `print`), settings and config. Say which are mandatory for new code.

## Dev commands

<!-- crew:discoverable capability=cli:uv -->

> **▸ Fill:** the project's dev-workflow commands (setup, lint, format, test) if a wrapper CLI or task runner ships them, and what each wraps.

## House rules

<!-- crew:optional -->

> **▸ Fill:** anything a Python author must not guess — typing strictness, import rules, logging, banned libraries, release or packaging steps.
