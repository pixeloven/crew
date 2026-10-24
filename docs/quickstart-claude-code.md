# Quickstart — Claude Code

## 1. Install and enable Crew

Add this at project or user scope:

```json
{
  "extraKnownMarketplaces": {
    "pixeloven": { "source": { "source": "github", "repo": "pixeloven/marketplace" }, "autoUpdate": true }
  },
  "enabledPlugins": { "crew@pixeloven": true }
}
```

Restart Claude Code; plugins load at session start.

### Enable packs per project

Crew can sit at either scope. Enable each pack only in the projects that use it,
in that project's `.claude/settings.json`:

```json
{
  "enabledPlugins": { "infra-skills@pixeloven": true }
}
```

or `claude plugin install infra-skills@pixeloven --scope project`. User scope
(`~/.claude/settings.json`, and the CLI's default) is the alternative for a pack
every project needs.

Every listed skill's description is paid on every turn. Claude Code budgets the
listing at `skillListingBudgetFraction` of the context window (default `0.01`),
or at `SLASH_COMMAND_TOOL_CHAR_BUDGET` chars when that variable is set.
Over budget it lists the least-used skills by name only, without warning, and
agents then pick the right skill less often. Leaving unused packs out of a
project keeps Crew's descriptions in the listing. Crew Doctor's
`description-cost.claude-code` row predicts the collapse and names both remedies.

## 2. Verify each layer separately

Free native checks:

```sh
claude plugin validate /absolute/resolved/crew/root --strict
claude --plugin-dir /absolute/resolved/crew/root plugin details crew
```

Settings prove enablement. `known_marketplaces.json` proves only the source,
location, and refresh timestamp. Read the marketplace clone's
`.claude-plugin/plugin.json` for the served version, and enumerate every
`installed_plugins.json` `crew@pixeloven` record for installed version and scope.
Only the current session catalogue proves what loaded.

A fresh `claude -p` check is billed. Crew Doctor must explain what it would add
and obtain explicit approval before running it.

The runtime should expose the seven roles: `lead`, `triage`, `investigator`,
`researcher`, `responder`, `reviewer`, and `implementer`. Its skill list should
contain namespaced entries such as `crew:doctor`. A loaded entry with no visible
description is loaded-but-undiscoverable, not healthy.

## 3. Add project-local skills and roles

Keep each project skill once at `.agents/skills/<name>/SKILL.md`, then symlink its
directory for Claude:

```sh
ln -s ../../.agents/skills/<name> .claude/skills/<name>
```

Project roles are `.claude/agents/<name>.md`. Plugin skills are namespaced as
`crew:<name>` and project skills are bare, so a same-named pair coexists rather
than one shadowing the other.

## 4. Onboard safely

Ask: **“onboard this project.”** The result is a read-only audit using one of the
shared profiles: `personas` for declared OpenClaw/persona runtimes, otherwise
`platform` when a capability was proven working, otherwise `portable`.

To edit, give a distinct current-run instruction to **apply the onboarding
findings**. Plain onboarding is never apply authorization. Onboarding preserves
mature entry files, safety tripwires, project delivery contracts, and runbook
pointers.
The supervising host verifies a fresh, non-persisted signal for that exact
invocation; saved, standing, reusable, and prior-run authority is rejected.
