---
name: openclaw-platform-operations
description: Generic OpenClaw gateway operations — the self-owned config model and deep-merge rule, Tool Search and the 128-tool cap, local-memory vs shared-KB, MCP tool-list caching, and the contextTokens landmine. Load when wiring an OpenClaw gateway's config, capabilities, memory, or tool budget.
tier: subject
requires: [cluster]
audience: [crew]
expects-local: [litellm-access-map]
---

# OpenClaw Platform Operations

Operational reference for running an OpenClaw gateway as a **platform surface** — how its config behaves, how it discovers tools, where its memory lives, and the landmines that block it silently. Generic OpenClaw product behavior; for identity/voice composition see `openclaw-agent-tuning`, and for the MCP access mechanism see `litellm-routing-model`.

**Audience:** an *operating* agent — any harness running these crew roles (Claude Code, pi.dev) that wires and runs OpenClaw gateways, the same way `argocd-deployment-patterns` is for operating ArgoCD or `comfyui` for operating ComfyUI. It is **not** loaded by the OpenClaw agents themselves (those run their own OpenClaw/ClawHub skill system). The subject is OpenClaw; the reader is whoever operates it.

## Config model — the gateway owns its config file

OpenClaw treats its config (a JSON file, e.g. `openclaw.json`) as a file it **owns and rewrites**, stamping a `meta` fingerprint on each write. This has one hard consequence for any external config injection:

- **Deep-merge, never overwrite.** A naked full-overwrite that lacks the `meta` fingerprint trips OpenClaw's **config-health guard**, which reverts the file back to its last valid state. External injection (init container, postStart, config job) must **deep-merge** into the existing file, preserving `meta`.
- **Deep-merge never deletes keys.** Because a merge only adds/updates, you cannot remove a setting by omitting it. To remove a key, run `openclaw config unset <path>` — dropping it from the merged input leaves the old value in place.

Practical injection pattern: read the current file, deep-merge your fields into it (keeping `meta`), write it back. An overwrite that "looks applied" but silently reverts a few seconds later is the classic symptom of skipping the merge.

## Tool Search — staying under the 128-tool cap and driving discoverability

A federated MCP surface can expose far more tools than a model can take. OpenAI caps a request at **128 tools**; lean local models overflow well before that. Tool Search defers the catalog behind meta-tools:

```json
"tools": { "toolSearch": { "enabled": true, "mode": "directory" } }
```

- In `directory` mode, large MCP/tool catalogs sit behind the meta-tools `tool_search` / `tool_describe` / `tool_call`, while a **bounded visible directory** of tools stays listed. This keeps the request under the 128-tool cap.
- It also drives **discoverability**: lean models otherwise never search for hidden tools, so a bounded directory is what makes them aware the deferred catalog exists.
- `experimental.localModelLean: true` auto-enables Tool Search — the right default for small-context local models.
- **Native tools stay direct.** Memory (`memory_search` / `memory_get`), read/write, and exec are not deferred behind the meta-tools; only the large federated catalog is.

This complements per-server `allowed_tools` scoping at the gateway (see `litellm-routing-model`): allowlisting narrows *what exists*, Tool Search defers *what's visible per request*.

## Memory — local per-agent vs shared knowledge base

Two distinct stores with different privacy scope; do not conflate them. This is a generic distinction any memory-capable surface faces (see `memory-substrate`):

| Store | Reached via | Scope | Backing |
|-------|-------------|-------|---------|
| **Local agent memory** | OpenClaw-native `memory_search` / `memory_get` | **Private** to the one agent | The agent's own `MEMORY.md` (and identity markdown) + a qmd-built index over it |
| **Shared knowledge base** | MCP (e.g. `vault` / `qmd_search`) | Shared across every surface | A shared corpus reached through the LiteLLM MCP federation |

Local memory is the agent talking to itself; the shared KB is the platform's common corpus. An agent's identity `MEMORY.md` is therefore **also a searchable local-memory source**, not just a character file. Granting an OpenClaw surface access to the shared KB is a capability grant like any other — add the KB group to its VK (see the capability-parity pattern in `litellm-routing-model`).

## Multi-agent: OpenClaw *has* it — we decline it by policy

OpenClaw supports sub-agents and agent-to-agent messaging. Personas being leaf surfaces is **our configuration decision**, not a missing capability — record it as such so nobody re-derives it, and so it stays reversible.

| Capability | Mechanism | Our posture |
|---|---|---|
| Sub-agents | `sessions_spawn` (non-blocking, push-based; `sessions_yield` to await; `context: isolated \| fork`) | unused |
| Cross-agent spawn | `sessions_spawn.agentId`, gated by `subagents.allowAgents` (**default: same-agent only**; `["*"]` opens it). `maxSpawnDepth` 1–5 (default 1), `maxConcurrent` 8 | **left at default** |
| Agent-to-agent messaging | `sessions_send` to another session on the same Gateway by `sessionKey` / `label` / `agentId`; `timeoutSeconds: 0` = fire-and-forget | unused |
| Swarm (experimental) | `tools.swarm.enabled`; Code Mode `agents.run()` with structured results, fan-out, `agents_wait`, `maxTotalPerGroup` backstop | **off** |
| Gateway `bindings[]` | inbound routing only — not dispatch | n/a |
| Cross-*instance* A2A | does not exist upstream and is not planned | genuinely unavailable |

**Why decline it.** Personas are *characters*, not fungible workers — the 8 identity layers in `openclaw-agent-tuning` exist to protect exactly what fan-out over personas would dilute. Adding spawn/message tools also spends tool budget against the 128-tool cap that small-context local models overflow well before.

**The escape hatch, if fan-out is ever wanted:** add a lean **non-persona `worker` agent id** and open `allowAgents` to that id only — upstream's own recommendation. Don't make companions dispatch.

**Reaching a persona from outside:** `openclaw agent --agent <id> --message-file <packet> --json` is the supported handle for a crew role to dispatch *into* a persona while the persona itself stays a leaf.

## MCP tool-list caching → roll the consumer on a VK change

An OpenClaw gateway caches its MCP tool list from the connection it makes at **startup**. A change to that VK's access groups (adding or removing a capability) is invisible until the gateway reconnects — **restart the pod** after changing its VK. This is rollout landmine (c) in `litellm-routing-model`, seen from the consumer side.

## contextTokens landmine — the gateway can block permanently

If `contextTokens` is set **below `reserve + base prompt`**, the gateway blocks permanently: the first prompt overflows the window, compaction cannot recover (there is nothing to compact away), and the gateway stays wedged. Only a **config fix plus a pod restart** recovers it. Size `contextTokens` with headroom above the base system prompt plus the configured reserve before deploying.

## See also

- `litellm-routing-model` — MCP access groups, the capability-parity pattern, per-server `allowed_tools`, and the rollout landmines
- the project's protected-seams registry local skill (e.g. Harmony's `harmony-protected-seams`) — the MCP access boundary is typically a registry seam
- `openclaw-agent-tuning` — identity composition (the 8 layers), workspace files, model-specific behavior
- `memory-substrate` — the platform memory surfaces and where local agent memory sits among them
