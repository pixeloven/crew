# harmony-crew

A cross-project **agent foundation** for the projects I own — one shared skill tree, consumed by **four harnesses**:

| Harness | What it runs | Consumes | How |
|---------|-------------|----------|-----|
| **Claude Code** | operator/dev sessions + subagents | the **full** foundation (8 role agents + all skills) | plugin (this repo's marketplace) |
| **pi.dev** | autonomous workers | the **full** foundation (8 role agents + all skills) | pi package |
| **OpenAI Codex** | dev sessions (CLI / IDE / cloud) + subagents | `AGENTS.md` natively + the full skill catalog; **dispatches subagents** (crew roles not yet rendered to `.codex/agents/`) | skills copied into `.agents/skills/` (pinned tag) |
| **OpenClaw** | assistant/companion agents (personas) | a **consumption slice** of skills (no roles) | skills installed into the gateway |

The same `skills/<name>/SKILL.md` tree feeds all four. Claude Code and pi.dev run the **8 crew roles** (`lead`, `implementer`, …) with a per-runtime agent variant. **Codex** reads the same `AGENTS.md` and skills and dispatches subagents from the routing table's instruction — the crew roles aren't rendered to its `.codex/agents/` format yet, so it delegates to its own built-ins guided by the table. **OpenClaw** runs project personas rather than roles, and by deliberate policy keeps them as leaves (it *has* dispatch — see `openclaw-platform-operations`), consuming only the skill *slice* that lets an agent *use the platform*.

> **Status.** Seeded from Harmony's agents + skills, now generalized: the catalog carries generic patterns, and each consumer's concrete values live in its own overlay via declared local-skill **slots** (starter stubs: [`templates/local-skills/`](templates/local-skills/)). Harmony remains the worked example throughout.

## Get started

1. Follow your harness's quickstart: **[Claude Code](docs/quickstart-claude-code.md)** · **[pi.dev](docs/quickstart-pi.md)** · **[OpenAI Codex](docs/quickstart-codex.md)** · **[OpenClaw](docs/quickstart-openclaw.md)**.
2. Ask an agent to **"onboard this project to harmony-crew"** — the `onboarding` skill generates (or audits) your `AGENTS.md` and tailors it to the capabilities you actually have.
3. Any time after: **"run the doctor"** — verifies the install, probes which platform capabilities the session can reach, and reports unfilled local-skill slots.

## Supported harnesses & the consumption model

**Four frontmatter fields decide where a skill goes, who gets it, and what it expects back** (browsable inventory: [`docs/CATALOG.md`](docs/CATALOG.md)):

- **`tier`** — `concept` (platform-generic patterns) vs `subject` (about a specific tool/product). Project-specific values never live here — they go in the consumer's **local** overlay.
- **`requires`** — the runtime capability the skill's guidance operates: `[]` (portable — works on a bare repo), `mcp:<group>` (a federated MCP capability granted via the consumer's virtual key), `cluster` (live cluster/platform access), or `external:github|web` (public platforms). This is the axis onboarding profiles and doctor checks filter on.
- **`audience`** — `[crew]` (the Claude Code / pi.dev role harnesses) or `[crew, persona]`. Skills with `persona` form the **OpenClaw consumption slice**, generated into [`slices/openclaw.txt`](slices/openclaw.txt); the gateway install consumes that file, so the slice cannot drift from frontmatter.
- **`expects-local`** *(optional)* — the consumer-local skill **slots** this skill defers concrete values to (`platform-conventions`, `topology`, `protected-seams`, …). Slot definitions and starter stubs live in [`templates/local-skills/`](templates/local-skills/); a consumer fills a slot with its own local skill (Harmony's fillings are the worked example).

**Operator vs consumption — the key OpenClaw distinction.** Some skills are *about* OpenClaw but are for whoever **builds/tunes** a gateway (a Claude Code or pi.dev dev): `openclaw-platform-operations` (config model, Tool Search, rollout), `openclaw-agent-tuning` (identity layers). These are **operator skills** — they are **not** installed into OpenClaw agents. The **consumption slice** (below) is the opposite: skills an OpenClaw agent loads to *use* the platform.

## Platform capabilities — what these skills enable, per harness

| Capability | Skill(s) | Claude Code | pi.dev | Codex | OpenClaw agents |
|-----------|----------|:---:|:---:|:---:|:---:|
| **Shared knowledge base** (search / read / contribute) | `knowledge-base-access`, `memory-substrate`, `vault-tools` | ✓ | ✓ | ✓ | ✓ *(slice: `knowledge-base-access`)* |
| **Agent-local memory** (private recall) | `knowledge-base-access`, `memory-substrate` | ✓ | ✓ | ✓ | ✓ *(slice: `knowledge-base-access`)* |
| **Web search** | `searxng-search` | ✓ | ✓ | ✓ | ✓ *(slice)* |
| **Image generation** | `comfyui` | ✓ | ✓ | ✓ | ✓ *(slice)* |
| **Browser** (rendered pages, screenshots, interaction) | `browser` | ✓ | ✓ | ✓ | — |
| **Code intelligence** (SAST, AST/structural, LSP) | `codeintel` | ✓ | ✓ | ✓ | — |
| **Cluster ops** (ArgoCD reads + GitOps patterns) | `argocd-deployment-patterns` | ✓ | ✓ | ✓ | — |
| **Secrets / credentials** | `secret-management-patterns` | ✓ | ✓ | ✓ | — |
| **LiteLLM / MCP federation** | `litellm-routing-model` | ✓ | ✓ | ✓ | — |
| **Voice** (STT/TTS wiring — channel-level, not an agent tool) | `voice` | ✓ | ✓ | ✓ | — |
| **Planning · review · orchestration** | `plan-*`, `pr-review-checklist`, `orchestration-patterns`, seam skills | ✓ | ✓ | ✓* | — |
| **Build / tune OpenClaw** (operator) | `openclaw-platform-operations`, `openclaw-agent-tuning` | ✓ | ✓ | ✓ | — |

*✓\** = Codex loads the planning/review disciplines and can dispatch subagents; the crew roles are not yet rendered to `.codex/agents/`, so delegation targets its built-in agents. *✓ (slice)* = part of the OpenClaw **consumption slice**. The machine-readable slice is [`slices/openclaw.txt`](slices/openclaw.txt), generated from `audience` frontmatter (currently `searxng-search`, `comfyui`, `knowledge-base-access`); `memory-substrate` and `vault-tools` are crew-side references, not slice members. Actual availability of a capability at runtime also depends on the consumer's LiteLLM VK access groups (see `litellm-routing-model`) — the skill is the guidance; the VK grants the tools.

## What's in the box

**8 role agents**, single-sourced in `roles/<role>/` (shared `body.md` + per-runtime frontmatter + optional runtime-context appendix) and rendered by `scripts/render_roles.py` into `agents/*.md` (Claude format) and `pi-agents/role-*.md` (pi format): `lead`, `triage`, `investigator`, `researcher`, `responder`, `librarian`, `reviewer`, `implementer`. (Not used by OpenClaw.) Edit `roles/`, never the rendered trees — CI fails on drift.

**41 skills** (`skills/<name>/SKILL.md`), each carrying schema-v2 frontmatter — `tier`, `requires`, `audience` — with the full inventory generated into [`docs/CATALOG.md`](docs/CATALOG.md). There is deliberately no `project` tier — deployment-specific skills (node IPs, one cluster's topology) belong in the consumer's **local** repo. In-skill residue is still being generalized backward incrementally.

## Install

Per-harness walkthroughs with verification steps live in the quickstarts (see *Get started*); the blocks below are the copy-paste cores.

### Claude Code

Enable the plugin in `.claude/settings.json` (or `~/.claude/settings.json` for all your projects):

```json
{
  "extraKnownMarketplaces": {
    "harmony-crew": { "source": { "source": "github", "repo": "ductiletoaster/harmony-crew" }, "autoUpdate": true }
  },
  "enabledPlugins": { "harmony-crew@harmony-crew": true }
}
```

No `ref` ⇒ tracks the latest release on `main` (`autoUpdate` pulls it on startup). The project keeps its own `.claude/skills/` + `.claude/agents/` overlay, which shadows foundation entries when names collide.

### pi.dev

In `.pi/settings.json` — pin the tag for reproducible builds:

```json
{ "packages": ["npm:pi-subagents@0.28.0", "git:github.com/ductiletoaster/harmony-crew@v0.12.0"] }
```

The project adds its own `.pi/skills/` + `.pi/agents/` overlay; pi walks it from cwd to git root before the package.

### OpenAI Codex

Codex reads `AGENTS.md` natively — install is skills + MCP only. Copy the catalog into `~/.agents/skills/` (user-level; or the repo's `.agents/skills/` to vendor it) at a pinned tag, and point `~/.codex/config.toml` at the LiteLLM gateway with the surface's own VK:

```toml
[mcp_servers.litellm]
url = "https://<your-litellm-host>/mcp"
bearer_token_env_var = "LITELLM_API_KEY"
```

Full walkthrough (copy snippet, VK guidance, what Codex doesn't get): [docs/quickstart-codex.md](docs/quickstart-codex.md).

### OpenClaw

OpenClaw agents run a different runtime (ClawHub skills + persona workspace files), so they don't load the plugin/package — instead the **consumption slice** is installed into the gateway's managed skills dir. The gateway's `init-skills` step clones harmony-crew (pinned tag) and installs the slice via OpenClaw's native installer:

```sh
# init container (a GH token is needed only for a PRIVATE foundation repo; mount it init-only)
git clone --depth 1 -b v0.12.0 https://<token>@github.com/ductiletoaster/harmony-crew /tmp/hc
while read -r s; do
  openclaw skills install /tmp/hc/skills/$s --global --as $s      # → ~/.openclaw/skills (auto-loaded)
done < /tmp/hc/slices/openclaw.txt
```

Then per-agent visibility is set with the gateway's `agents.list[].skills` allowlist. harmony-crew's `SKILL.md` frontmatter (`tier`/`category`) is ignored by OpenClaw — the file installs and loads as-is. Worked example: `ductiletoaster/harmony`'s `openclaw-{agents,companions}.yaml`.

## Versioning & maintenance

One semver line drives all consumers — `plugin.json` == `package.json` == git tag `vX.Y.Z`. **Claude Code** tracks `main` (always latest); **pi.dev** and **OpenClaw** pin the tag — bump the pin to update. The full versioning contract, repo layout, editing rules, and CI gates live in [`docs/MAINTAINERS.md`](docs/MAINTAINERS.md).

## Onboarding — the `onboarding` skill

Installing the foundation gives a project the agents + skills, but not an entry file — agent *behavior* is driven by a repo-local `AGENTS.md` per project. The [`onboarding`](skills/onboarding/SKILL.md) skill applies the foundation's opinion to a project — ask an agent to *onboard this project to harmony-crew*:

- **New project** → generates `AGENTS.md` from [`templates/AGENTS.md`](templates/AGENTS.md), inferring what it can.
- **Existing project** → audits `AGENTS.md`/`CLAUDE.md`, routes delegation to the foundation's agents, and **moves facts/conventions out of the entry file into local skills**.
- **Re-runnable** as the project grows. If the project runs **OpenClaw**, onboarding also flags wiring the gateway's consumption-slice install (see the OpenClaw install above).

**Merge-don't-replace**: the foundation supplies the behavioral spine; the project fills its specifics. Worked example: [Harmony's filled `AGENTS.md`](https://github.com/ductiletoaster/harmony/blob/main/AGENTS.md).

## First consumer

`ductiletoaster/harmony` consumes this foundation across **all three harnesses** — Claude Code + pi.dev run the crew roles; its OpenClaw gateways install the consumption slice — and layers its homelab-specific skills/roles on top. The reference example of the overlay model.
