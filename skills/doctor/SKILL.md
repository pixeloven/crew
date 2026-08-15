---
name: doctor
description: Health-check a project's harmony-crew install and report what actually works — plugin/package present, roles resolvable, which platform capabilities this session can reach, which consumer-local skill slots are unfilled, and which onboarding profile fits. Load when asked to run the doctor, verify or debug the foundation install, check onboarding status, or answer "what capabilities do I have here".
tier: concept
requires: []
---

# Doctor

Run the checks below in order, then produce the report. Absence of a platform is a **profile**, not a failure — this skill never treats "no cluster, no gateway" as an error; it records what's reachable and recommends the matching posture. The foundation itself needs nothing but a repo.

## The checks

**1. Installation.**
- Claude Code: `.claude/settings.json` (project or user) has the `harmony-crew` marketplace + `enabledPlugins` entry. pi.dev: `.pi/settings.json` packages include `harmony-crew` (note the pinned tag — report if it lags the installed catalog's version). OpenAI Codex: the catalog is present in the repo's `.agents/skills/` or `~/.agents/skills/` (report which, and the pinned tag if recorded), and `config.toml` has an `mcp_servers` entry for the LiteLLM gateway with a `bearer_token_env_var`.
- The seven roles resolve: the harness's agent list contains `lead`, `triage`, `investigator`, `researcher`, `responder`, `reviewer`, `implementer` (or the `role-*` pi variants). If skills load but agents don't (or vice versa), the install is partial — say which half. On **Codex**, the foundation does not yet render `.codex/agents/*.toml`, so report the roles as *not yet rendered for this harness* (a known gap, not a broken install) and confirm instead that the `AGENTS.md` routing table is present — that table is what triggers Codex's delegation.

**2. Entry file.**
- A repo-root `AGENTS.md` exists. Claude Code repos also want a `CLAUDE.md` containing `@AGENTS.md`.
- It is *behavioral*: short, with the routing table, and no fact-stuffing (infra tables, credential paths, command catalogs). If facts have accreted, recommend re-running `onboarding`.
- The ▸ Fill blocks are actually filled (ask-list, verification commands, local-skills map, tripwires) — an unfilled template is a half-onboarded project.

**3. Capability probe.** The foundation's own skills need only `external:github` — check `gh auth status`. Beyond that, probe whatever **the project's local skills** declare they need: if the overlay ships knowledge-base, gateway, or cluster skills, confirm the corresponding tools are actually in this session's tool list and say which are reachable. Present = granted; absent = not granted, which is a fact to report rather than an error.

**4. Local slots.** For each slot the installed skills declare in `expects-local:` (`platform-conventions`, `topology`, `protected-seams`, `litellm-access-map`, `secret-paths`, `vault-ops`, `agent-runtime`): does the project's overlay (`.claude/skills/`, `.pi/skills/`) or its `AGENTS.md` local-skills map name a skill filling it? Only flag slots that matter for the project's profile — a portable-profile repo doesn't need `topology`. Starter stubs: the foundation's `templates/local-skills/`.

**5. Intake prerequisites** (only if the project routes work through Triage): `gh label list` shows the `domain:*` labels (and `agent:queued` / `triage:needs-clarification` if used). Missing labels mean Triage's routing silently no-ops.

**6. Shadowing** — the check that catches silent staleness. A project-level `.claude/agents/` or `.claude/skills/` entry **overrides** the plugin's version of the same name. List any collisions and say which copy wins, because a stale local copy makes foundation updates invisible with no error. If a local copy is an old snapshot rather than a deliberate override, that's the finding.

## The report

A table — one row per check: **check | status (OK / MISSING / DEGRADED / N/A) | evidence | next action**. Then two closing lines:

- **Profile:** `portable` (the foundation's catalogue alone — its skills need nothing but a repo and, for a few, GitHub) or `platform` (the project's overlay adds capability skills whose tools this session can reach — name which). This is the input `onboarding` uses to tailor the skills index.
- **Top action:** the single highest-leverage fix (or "healthy — nothing to do").

Keep it honest: report what you *verified*, not what config files claim. A tool listed but never probed is "present", not "working".
