---
name: doctor
description: Health-check a project's harmony-crew install and report what actually works — plugin/package present, roles resolvable, which platform capabilities this session can reach, which consumer-local skill slots are unfilled, and which onboarding profile fits. Load when asked to run the doctor, verify or debug the foundation install, check onboarding status, or answer "what capabilities do I have here".
tier: concept
requires: []
audience: [crew]
---

# Doctor

Run the checks below in order, then produce the report. Absence of the platform is a **profile**, not a failure — this skill never treats "no cluster, no gateway" as an error; it records what's reachable and recommends the matching posture.

## The checks

**1. Installation.**
- Claude Code: `.claude/settings.json` (project or user) has the `harmony-crew` marketplace + `enabledPlugins` entry. pi.dev: `.pi/settings.json` packages include `harmony-crew` (note the pinned tag — report if it lags the installed catalog's version). OpenAI Codex: the catalog is present in the repo's `.agents/skills/` or `~/.agents/skills/` (report which, and the pinned tag if recorded), and `config.toml` has an `mcp_servers` entry for the LiteLLM gateway with a `bearer_token_env_var`.
- The eight roles resolve: the harness's agent list contains `lead`, `triage`, `investigator`, `researcher`, `responder`, `librarian`, `reviewer`, `implementer` (or the `role-*` pi variants). If skills load but agents don't (or vice versa), the install is partial — say which half. On **Codex**, the foundation does not yet render `.codex/agents/*.toml`, so report the roles as *not yet rendered for this harness* (a known gap, not a broken install) and confirm instead that the `AGENTS.md` routing table is present — that table is what triggers Codex's delegation.

**2. Entry file.**
- A repo-root `AGENTS.md` exists. Claude Code repos also want a `CLAUDE.md` containing `@AGENTS.md`.
- It is *behavioral*: short, with the routing table, and no fact-stuffing (infra tables, credential paths, command catalogs). If facts have accreted, recommend re-running `onboarding`.
- The ▸ Fill blocks are actually filled (ask-list, verification commands, local-skills map, tripwires) — an unfilled template is a half-onboarded project.

**3. Capability probe.** For each `requires:` class in the catalog (see `docs/CATALOG.md` in the foundation repo), test reachability from *this* session:
- `mcp:*` groups (kb, search, imagegen, browser, codeintel, coder, argocd) — check the session's tool list (or the harness's tool-search) for the corresponding federated tools (`qmd_search`/`vault_*`, `searxng-*`, `comfyui-*`, `browser-*`, `semgrep-*`, `coder-*`, `argocd-*`). Present = granted on this VK; absent = not granted (not necessarily an error — say which).
- `cluster` — can `kubectl get nodes` (or an equivalent read) succeed?
- `external:github` — is `gh auth status` healthy? `external:web` — is web search/fetch available?

**4. Local slots.** For each slot the installed skills declare in `expects-local:` (`platform-conventions`, `topology`, `protected-seams`, `litellm-access-map`, `secret-paths`, `vault-ops`, `agent-runtime`): does the project's overlay (`.claude/skills/`, `.pi/skills/`) or its `AGENTS.md` local-skills map name a skill filling it? Only flag slots that matter for the project's profile — a portable-profile repo doesn't need `topology`. Starter stubs: the foundation's `templates/local-skills/`.

**5. Intake prerequisites** (only if the project routes work through Triage): `gh label list` shows the `domain:*` labels (and `agent:queued` / `triage:needs-clarification` if used). Missing labels mean Triage's routing silently no-ops.

**6. OpenClaw wiring** (only if the project runs personas): the gateway's init-skills step installs from the foundation's `slices/openclaw.txt` at a pinned tag (not a hand-typed list); per-agent `skills` allowlists ⊆ the slice; each allowlisted skill's capability is granted on that agent's VK.

## The report

A table — one row per check: **check | status (OK / MISSING / DEGRADED / N/A) | evidence | next action**. Then two closing lines:

- **Profile:** `portable` (no platform capabilities reachable — the `requires: []` catalog is your working set), `platform` (some/all `mcp:*`/`cluster` reachable — name which), and/or `personas` (OpenClaw wired). This is the input `onboarding` uses to tailor the skills index.
- **Top action:** the single highest-leverage fix (or "healthy — nothing to do").

Keep it honest: report what you *verified*, not what config files claim. A tool listed but never probed is "present", not "working".
