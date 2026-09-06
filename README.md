# harmony-crew

A cross-project **agent foundation** for the projects I own — one shared skill tree, consumed by **three harnesses**:

| Harness | What it runs | Consumes | How |
|---------|-------------|----------|-----|
| **Claude Code** | operator/dev sessions + subagents | the **full** foundation (7 role agents + all skills) | plugin (this repo's marketplace) |
| **pi.dev** | autonomous workers | the **full** foundation (7 role agents + all skills) | pi package (`pi-subagents` ≥ 0.29.0) |
| **OpenAI Codex** | dev sessions (CLI / IDE / cloud) + subagents | `AGENTS.md` natively + all skills; **no crew roles** — it dispatches its built-in subagents | plugin (`codex plugin marketplace`, pinned tag) or skills vendored into `.agents/skills/` |

The same `skills/<name>/SKILL.md` tree feeds all three, and the same `AGENTS.md` drives all three. Claude Code and pi.dev additionally run the **7 crew roles**, rendered from one shared source so both get the same names, descriptions, and capability posture. **Codex cannot receive them**: its plugin format has no slot for agent roles, so there it reads the same `AGENTS.md` and skills and delegates to its own built-in subagents. That asymmetry is a property of the harness, not a gap in this repo — see [the Codex quickstart](docs/quickstart-codex.md#5-delegation--how-the-routing-table-works-here).

> **Scope.** This foundation is **agent methodology** — how agents plan, review, implement, delegate, and handle protected seams, plus stack conventions and the onboarding/doctor tooling. It is deliberately **portable**: its skills need nothing but a repo (a few use GitHub). Skills for *using* a platform's capabilities, or for *running* a platform, belong in that consumer's own overlay — see [`templates/local-skills/`](templates/local-skills/) for the slots the foundation defers to, and [`ductiletoaster/harmony`](https://github.com/ductiletoaster/harmony) for a filled example.

## How a skill is described

Three frontmatter fields. Agents don't read this metadata — every supported harness lists installed skills with their **descriptions** to the model on its own, so the description *is* the discovery interface and carries the whole trigger. The fields below serve humans and tooling; browsable inventory: [`docs/CATALOG.md`](docs/CATALOG.md).

- **`tier`** — `concept` (generic pattern) vs `subject` (about a specific tool/product).
- **`requires`** — what the skill's guidance needs at runtime. Almost everything here is `[]`; a few need `external:github`.
- **`expects-local`** *(optional)* — the consumer-local skill **slots** a skill defers concrete values to (`platform-conventions`, `topology`, `protected-seams`, …). Stubs in [`templates/local-skills/`](templates/local-skills/).

## What's in the box

**7 role agents**, single-sourced in `roles/<role>/` (one harness-neutral `role.yml` + shared `body.md` + optional runtime-context appendix) and rendered by `scripts/render_roles.py` into `agents/*.md` (Claude Code) and `pi-agents/*.md` (pi): `lead`, `triage`, `investigator`, `researcher`, `responder`, `reviewer`, `implementer`. Same names, same descriptions, same capability posture on both — only the frontmatter dialect differs, and the renderer owns that translation. A role declares **who it is and what it may touch**; it never pins a model, a reasoning level, or a turn budget — those are the dispatching session's to choose. Edit `roles/`, never the rendered trees — CI fails on drift.

**26 skills** (`skills/<name>/SKILL.md`), each carrying `tier`, `requires`, and optional `expects-local` frontmatter, with the full inventory generated into [`docs/CATALOG.md`](docs/CATALOG.md). Deployment-specific skills — node IPs, one cluster's topology, a gateway's access map — belong in the consumer's **local** overlay, never here.

## Install

Per-harness walkthroughs with verification steps live in the quickstarts (see *Get started*); the blocks below are the copy-paste cores.

### Claude Code

Enable the plugin in `.claude/settings.json` (or `~/.claude/settings.json` for all your projects):

```json
{
  "extraKnownMarketplaces": {
    "crew": { "source": { "source": "github", "repo": "pixeloven/crew" }, "autoUpdate": true }
  },
  "enabledPlugins": { "crew@crew": true }
}
```

No `ref` ⇒ tracks the latest release on `main` (`autoUpdate` pulls it on startup). The project keeps its own `.claude/skills/` + `.claude/agents/` overlay, which shadows foundation entries when names collide.

### pi.dev

In `.pi/settings.json` — pin the tag for reproducible builds:

```json
{ "packages": ["npm:pi-subagents@0.33.1", "git:github.com/pixeloven/crew@v0.33.0"] }
```

The project adds its own `.pi/skills/` + `.pi/agents/` overlay; pi walks it from cwd to git root before the package.

### OpenAI Codex

Codex reads `AGENTS.md` natively and reads this repo's `.claude-plugin/marketplace.json` directly — no `.codex-plugin/` needed:

```sh
codex plugin marketplace add pixeloven/crew --ref v0.33.0
codex plugin add crew@crew
```

Skills only — Codex plugins have no slot for agent roles. Vendoring the catalog into `.agents/skills/` at a pinned tag remains a supported alternative. Full walkthrough (what Codex does and doesn't get, the description-budget landmine): [docs/quickstart-codex.md](docs/quickstart-codex.md).

## Versioning & maintenance

One semver line drives all consumers — `plugin.json` == `package.json` == git tag `vX.Y.Z`. **Claude Code** tracks `main` (always latest); **pi.dev** and **Codex** pin the tag — bump the pin to update. The full versioning contract, repo layout, editing rules, and CI gates live in [`docs/MAINTAINERS.md`](docs/MAINTAINERS.md).

## Onboarding — the `onboarding` skill

Installing the foundation gives a project the agents + skills, but not an entry file — agent *behavior* is driven by a repo-local `AGENTS.md` per project. The [`onboarding`](skills/onboarding/SKILL.md) skill applies the foundation's opinion to a project — ask an agent to *onboard this project to harmony-crew*:

- **New project** → generates `AGENTS.md` from [`templates/AGENTS.md`](templates/AGENTS.md), inferring what it can.
- **Existing project** → audits `AGENTS.md`/`CLAUDE.md`, routes delegation to the foundation's agents, and **moves facts/conventions out of the entry file into local skills**.
- **Re-runnable** as the project grows.

**Merge-don't-replace**: the foundation supplies the behavioral spine; the project fills its specifics. Worked example: [Harmony's filled `AGENTS.md`](https://github.com/ductiletoaster/harmony/blob/main/AGENTS.md).

## First consumer

`ductiletoaster/harmony` consumes this foundation across all three harnesses and layers its own platform skills — knowledge base, gateway routing, cluster operations, persona tuning — on top. It is the reference example of the overlay model, and of the boundary: everything platform-specific lives there, not here.
