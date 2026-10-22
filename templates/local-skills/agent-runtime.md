---
name: <project>-agent-runtime
description: <Project>'s autonomous agent runtime contracts — dispatch CLI, execution environment, exit codes, result format, retry semantics, and credentials. Load when writing or debugging autonomous agent workflows. The generic design guidance is the foundation's autonomous-agent-design skill.
---

## Runtime architecture

> **▸ Fill:** how autonomous work is dispatched and where it executes (e.g. a Workflow engine + orchestrator, a queue + worker pool), and the namespace/environment it runs in.

## Contracts

> **▸ Fill:** exit-code semantics, the structured result format and its path, and the retry policy tied to them. These are usually seam material — reference them from your protected-seams registry.

## Credentials

> **▸ Fill:** the scoped credentials automated runs use (never the operator's interactive ones), by path reference.

## Commands

> **▸ Fill:** the dispatch/reconcile commands an operator or Lead uses.

## Capabilities

Skills name capabilities (`cli:`, `mcp:`, `external:`); this table names the tool that provides each one here. Onboarding generates it from `scripts/crew_inventory.py` and edits only the text between the markers. It records the provider name, kind and state, never paths, versions or secrets. Doctor reports a map that differs on this machine.

> **▸ Fill:** for each row, the operator command that stands in when the provider is absent or unavailable. Onboarding keeps what you write here.

<!-- crew:capability-map begin -->
<!-- crew:capability-map end -->
