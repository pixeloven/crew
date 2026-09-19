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
