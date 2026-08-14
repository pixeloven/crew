---
name: litellm-routing-model
description: LiteLLM gateway auth model — virtual keys, teams, MCP access groups, the capability-parity pattern, and the rollout landmines. Load before touching VK scopes, MCP server registrations, or granting a surface a new capability.
tier: concept
requires: [cluster]
audience: [crew]
expects-local: [litellm-access-map, protected-seams]
---

# LiteLLM Routing Model

A LiteLLM gateway is both the LLM router and the MCP federation point. One bearer credential — a **virtual key (VK)** — carries both concerns: model routing *and* MCP tool scope. There is no separate MCP credential.

> This skill is the generic mechanism. The concrete VK↔group matrix for a given deployment — the aliases, which surface holds which key, the 1Password paths, the team name — lives in that consumer's **local skill** (e.g. a `litellm-routing` local skill), not here.

## Two-level MCP access enforcement

Tool visibility on `/mcp` for any consumer is the **intersection** of three sets:

1. **Server → groups.** Each MCP upstream is registered in the LiteLLM proxy config `mcp_servers:` block with `access_groups`. Config-as-code — change via PR, not the admin UI.
2. **Team → allowed groups.** The team's `object_permission.mcp_access_groups` is the allowlist a member VK can opt into — a **hard ceiling**. DB entity — managed via `/team/update` with the master key.
3. **VK → opted-in groups.** The key's `object_permission.mcp_access_groups`, capped by the team ceiling.

```
visible tools = server.access_groups  ∩  team.mcp_access_groups  ∩  VK.mcp_access_groups
```

### Two fail-open gotchas

Both fail *open*, not closed — get them wrong and a surface silently over-grants. These are LiteLLM behaviors that have shifted across releases — characterized on v1.86.2; **re-verify after any LiteLLM upgrade** (the exact deployed version is a project-local fact):

- **Zero-match group = UNRESTRICTED.** A VK whose group set matches **no** registered server is treated as unrestricted, not as "no tools." You cannot express "no MCP" via an empty/zero-match group. Give such a VK a minimal **read-only floor group** (one that maps to a low-consequence search/read server) instead.
- **No groups = inherit the team allowlist.** A VK with no `mcp_access_groups` set inherits the team's *full* allowlist — the over-broad default. **Always set groups explicitly** on every VK.

After `/team/update`, the proxy's permission cache needs one retried request before changes take effect.

## Capability-parity pattern — grant capability Y to surface X

The thesis: every platform capability (knowledge base, cluster ops, image generation, web search, memory) is an MCP access group, and **any** surface — an OpenClaw gateway, a web app, a chat UI, a workstation — is granted that capability through the same three-set mechanism. "Give surface X capability Y" is one repeatable procedure, not per-surface bespoke wiring:

1. **Ensure a group exists for capability Y** — i.e. the server(s) backing Y carry a shared `access_groups` label in the proxy config.
2. **Add group Y to X's VK** (`mcp_access_groups`), keeping the VK's group set explicit and minimal.
3. **Ensure the team allows group Y** — the VK is capped by the team ceiling, so Y must be in the team's allowlist too (see rollout landmine (a)).
4. **Roll the consumer** if it caches its MCP tool list at startup (see rollout landmine (c)).

Revoking a capability is the same procedure in reverse: remove the group from the VK (never leave it groupless — see the no-groups gotcha), and roll the consumer.

## Rollout landmines — config-as-code is inert on live entities

Editing config-as-code does **not** mutate live DB entities or reload a running proxy. Each capability change has a manual step that config edits alone won't perform:

- **(a) New access group → imperative team update.** A new group must be added to the team allowlist via `/team/update` with the master key. VK-seed/bootstrap jobs are typically *create-if-absent* and never mutate a live team or key — so a config-as-code edit adding a group is inert on live entities until the imperative update runs.
- **(b) New MCP server → restart the LiteLLM deployment.** The proxy reads `mcp_servers` from a static config (e.g. a ConfigMap) at startup; there is no hot-reload. A newly registered upstream is invisible until the deployment restarts. (`PUT /v1/mcp/server` 404s on config-defined servers — they are not DB-managed.)
- **(c) VK group change → roll the caching consumer.** A consumer that caches its MCP tool list from a startup connection (e.g. an OpenClaw gateway) will not see a VK's new/removed groups until it reconnects. Restart the consumer pod after changing its VK.

## Per-server tool scoping and the tool-count cap

Two distinct pressures push toward narrowing a server's exposed tools:

- **Scope / least-privilege.** Only per-server `allowed_tools` allowlisting reliably restricts which of a server's tools are exposed (as of v1.86.2 — `disallowed_tools` was broken; re-verify on upgrade). Use it to expose a low-privilege subset of a broad server (e.g. only the generation tools of an image server that also carries host-path/manifest operations — see `comfyui`).

> **Allowlisting is name-based — a tool that takes its destructive action as an *argument* cannot be gated.** `allowed_tools` filters by tool name, so if one tool multiplexes several operations behind a parameter, allowing it allows all of them. Concrete case: Coder's `create_workspace_build` takes `transition: start|stop|delete`, which makes "allow start and stop but never delete" **inexpressible at the gateway** (see `coder-workspace-dispatch`). Before granting a capability group, check whether any of its tools multiplex a destructive verb; if one does, the gateway is not where you enforce that boundary — you need upstream-side scoping (a narrower service identity, a restricted role) or you accept the destructive verb as part of the grant. Audit for this whenever a new server joins a group.
- **Tool-count budget.** Large catalogs blow the model's tool-count limit — OpenAI caps a request at **128 tools**, and small-context local models overflow well before that. Mitigate with per-server `allowed_tools`, tightly-scoped groups, and/or the consumer's **Tool Search** (defers a large catalog behind meta-tools — see `openclaw-platform-operations`).

## Rules

- **New consumer surface → new VK** with explicit groups. Add an ESO/secret entry only if a pod actually mounts it (same-PR consumer rule — see `secret-management-patterns`).
- **Small-context local models** need tightly-scoped groups; the full operator catalog overflows a small prompt before user input arrives. See `openclaw-agent-tuning`.
- **Admin operations** use the master key against `/key/*`, `/team/*`. Never echo keys into output; pass via env var. The credential paths live in the consumer's local secret skill.
- **MCP servers live in the config, not the DB.** Edit the config and restart the deployment (landmine (b)).
- **The concrete VK↔group matrix** (aliases, per-surface keys, 1Password fields, team name) is deployment-specific — it lives in the consumer's local skill, not here.

## See also

- the project's protected-seams registry local skill (e.g. Harmony's `harmony-protected-seams`) — the access-group intersection is a protected boundary
- `seam-detection` — how to spot a group/allowlist/`access_groups` change in a diff
- `openclaw-platform-operations` — Tool Search, config model, and consumer-roll for OpenClaw surfaces
- `comfyui` — per-server `allowed_tools` scoping for a privileged image server
- `secret-management-patterns` — the VK's 1Password → ESO credential path
