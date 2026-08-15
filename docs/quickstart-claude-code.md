# Quickstart — Claude Code

From zero to a working crew in four steps. Everything here is also what the `doctor` skill verifies.

## 1. Install the plugin

Add to your project's `.claude/settings.json` (or `~/.claude/settings.json` for all projects):

```json
{
  "extraKnownMarketplaces": {
    "harmony-crew": { "source": { "source": "github", "repo": "ductiletoaster/harmony-crew" }, "autoUpdate": true }
  },
  "enabledPlugins": { "harmony-crew@harmony-crew": true }
}
```

No `ref` ⇒ tracks the latest release on `main`; `autoUpdate` pulls it on startup.

## 2. Restart and verify

**Restart Claude Code** — plugins load at startup, not live. Then verify: the agent list (visible when dispatching, or via `/agents`) should show the seven roles (`lead`, `triage`, `investigator`, `researcher`, `responder`, `reviewer`, `implementer`), and the skill list should include foundation skills like `platform-glossary`. If neither appears, the marketplace fetch failed — check the repo is reachable from your machine.

## 3. Decide your autonomy posture

The foundation's `AGENTS.md` template assumes **act-then-report**: tool use pre-approved via

```json
{ "permissions": { "defaultMode": "dontAsk" } }
```

in `.claude/settings.json`. This is a deliberate choice, not a default — without it, the template's "never pause to ask" posture and the permission prompts will fight each other. If you prefer prompts, keep the default mode and delete the pre-approval language when onboarding generates your `AGENTS.md`.

## 4. Onboard the project

Ask an agent: **"onboard this project to harmony-crew"**. The `onboarding` skill will run the `doctor` checks, pick an onboarding profile (portable / platform / personas — driven by which capabilities are actually reachable), generate or audit your `AGENTS.md` (plus a one-line `CLAUDE.md` containing `@AGENTS.md`), and propose local skills for your project's specifics — starter stubs live in `templates/local-skills/`.

Your project's own skills and agents live in `.claude/skills/` and `.claude/agents/`; they **shadow** foundation entries on name collision.

## Anytime after

- **"run the doctor"** — re-verify the install, see which capabilities your session can actually reach, and which local-skill slots are still unfilled.
- Re-run onboarding whenever `AGENTS.md` has accreted facts — it moves them back into skills.
