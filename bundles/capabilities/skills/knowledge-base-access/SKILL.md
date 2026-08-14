---
name: knowledge-base-access
description: How an agent consumes the platform's knowledge — searching/reading/contributing to the shared vault knowledge base vs. its own private local memory. Load when you need durable or org-wide knowledge, or want to record a finding.
tier: concept
requires: [mcp:kb]
audience: [crew, persona]
expects-local: [litellm-access-map]
---

# Knowledge-Base Access

Every platform agent has **two complementary knowledge layers**. Reach for the right one — they are different stores and nothing in one is visible to the other.

| Layer | What it holds | Reach it with | Scope |
|-------|---------------|---------------|-------|
| **Shared KB (vault)** | The platform's durable corpus — runbooks, decisions, notes, research | `qmd_search-*` (search) + `vault_*` (read/write) MCP tools | shared across every agent + harness |
| **Agent-local memory** | *Your own* private recall — your workspace / memory files | your harness's local-memory tools (OpenClaw `memory_search`/`memory_get`; Claude Code auto-memory) | private to you |

**Which to reach for:** "what does the platform *know* about X — has this been decided / documented?" → **shared KB**. "what did *I* say, or what do I remember about the user or a past session?" → **local memory**.

## Using the shared KB

Availability depends on your virtual key's access groups (see `litellm-routing-model`); if a tool below isn't present, you weren't granted that capability.

- **Search first** — `qmd_search-query`: semantic + keyword search over the corpus; returns snippets with their source. This is the entry point.
- **Read a specific note** — `vault_readNote(path)` / `vault_getNote(path)` once search points you at one.
- **Contribute a finding** (only if you hold write access) — `vault_writeNote(title, body, source_agent, tags, kind)`. Set `source_agent` to *your own* id. If you're unsure a fact is durable, write `kind: fleeting` — the corpus promotes vetted fleeting notes later.
- Full `vault_*` catalog: `vault-tools`. The crew-workflow recall/persistence habits (Pre-Task Recall / Post-Session Persistence): `memory-substrate`.

## Using local memory

- Before answering questions about the **user**, a **past conversation**, or your **own prior work**, search your private memory with your harness's local-memory tool.
- Write durable *personal* facts to local memory, **not** the shared KB — that keeps the shared corpus clean.

## Boundaries

- **Don't put private or persona content in the shared KB** — it's read by every agent and the whole operator fleet. Personal/character material belongs in local memory.
- **Contributing back is a capability, not a default** — only write to the shared KB when you have a durable, org-relevant finding *and* your VK grants vault write.
- **Degrade gracefully** — if the KB is unreachable (no access group, or the gateway is down), fall back to local memory and say what you skipped.

## See also

- `memory-substrate` — the crew-workflow entry point and the fuller form of this skill (recall + persistence habits, write routing, the full two-tier table)
- `litellm-routing-model` — how your VK's access groups gate which KB tools you can reach
- `vault-tools` — the full `vault_*` tool reference and note-kind schema
