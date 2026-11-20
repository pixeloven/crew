# Quickstart — Claude Code

## 1. Install and enable Crew

Add this at project or user scope, replacing `vX.Y.Z` with a published Crew
release tag:

```json
{
  "extraKnownMarketplaces": {
    "pixeloven": {
      "source": { "source": "github", "repo": "pixeloven/crew", "ref": "vX.Y.Z" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": { "crew@pixeloven": true }
}
```

Restart Claude Code; plugins load at session start. The CLI equivalent is
`claude plugin marketplace add pixeloven/crew#vX.Y.Z`, then
`claude plugin install crew@pixeloven`.

The `ref` is the release gate. The catalogue serves Crew and its packs from
this repo by relative path, so one tag pins all of them, and Claude Code
re-fetches each plugin when its `version` changes at the new ref. Without a
`ref`, the marketplace follows the default branch and every merged release
arrives on the next refresh. To upgrade, read the `### Consumer impact` section
of every [CHANGELOG](../CHANGELOG.md) release between your tag and the new one,
change `ref` in settings, run `claude plugin marketplace add
pixeloven/crew#<new tag>`, then `claude plugin update crew@pixeloven` (and each
enabled pack).

**Moving from `pixeloven/marketplace` (before 0.67.0).** Edit the settings entry
first: change `extraKnownMarketplaces.pixeloven.source` to the block above.
Then run `claude plugin marketplace add pixeloven/crew#vX.Y.Z` with the same
source, and `claude plugin update` for each installed plugin. The marketplace
name and plugin IDs stay the same, so `enabledPlugins` keeps working. Two
pitfalls:

- Running `marketplace add` with the new source while settings still name the
  old one fails ("source doesn't match its extraKnownMarketplaces entry").
  Change the settings entry first.
- **Never run `claude plugin marketplace remove pixeloven`** to migrate or move
  the ref. It uninstalls every plugin from that marketplace and empties their
  `enabledPlugins` entries.

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

The runtime should expose the six roles: `lead`, `triage`, `investigator`,
`researcher`, `reviewer`, and `implementer`. Its skill list should
contain namespaced entries such as `crew:doctor`. A loaded entry with no visible
description is loaded-but-undiscoverable, not healthy.

Five roles are dispatched from your session. `lead` is the exception: it plans
with you and dispatches the others, so start the session as Lead instead of
dispatching it:

```sh
claude --agent crew:lead
```

That session has no Edit tools, so Lead hands write work to `implementer`.

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
