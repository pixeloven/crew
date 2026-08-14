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
