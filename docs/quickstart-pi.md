# Quickstart — pi.dev

## 1. Install a role-discoverable release

Pin a published Crew release for reproducibility; replace `vX.Y.Z` with the
chosen tag:

```json
{
  "packages": [
    "npm:pi-subagents@0.81.0",
    "git:github.com/pixeloven/crew@vX.Y.Z"
  ]
}
```

Crew must be `v0.35.0` or newer. Earlier rendered Pi roles omitted frontmatter
`name:`; pi-subagents silently drops such files. Read the configured pin from
settings and the resolved version from the checkout's
`.claude-plugin/plugin.json`. Do not use `git describe` for package version.

Crew `v0.39.0` and newer require `pi-subagents` `>=0.62.0`. The roles express
their write posture with `excludeTools`, which older pi-subagents ignores, so
every role would silently receive pi's full default tool set, `write` and `edit`
included. Crew declares the tested range `>=0.62.0 <0.82.0` as its peer
dependency; `0.81.0` is the newest release verified to discover every role as
`crew.<role>` with its `excludeTools`. Treat a newer minor as untested until
Crew widens the range.

### Enable packs per project

Add each pack to the `packages` of the project that uses it, in `.pi/settings.json`
(`pi install git:github.com/pixeloven/<pack>@vX.Y.Z -l`), rather than to
`~/.pi/agent/settings.json`. User settings are the alternative for a pack every
project needs. Pi lists every visible skill's description in full in every
session, with no budget, so each pack a project doesn't use is pure cost there.
A package's `skills` filter (`"!skills/<name>"`) narrows one pack further.

## 2. Verify runtime discovery

In the intended Pi runtime, run its native `/subagents-doctor`. It should list
the seven Crew roles under their package-qualified names (`crew.lead`,
`crew.triage`, `crew.investigator`, `crew.researcher`, `crew.responder`,
`crew.reviewer`, `crew.implementer`) and the package skill tree. Package skill and role
discovery are separate; report which half failed.

If skills appear but roles do not, inspect both the package's
`pi.subagents.agents` manifest entry and each role's `name:` frontmatter. These
are separate, historically observed silent-failure seams.

Do not substitute another harness's result for Pi runtime evidence. `pi -p` or
any prompt-mediated fresh-session probe is billed and requires explicit approval.

## 3. Dispatch the qualified name

Every Crew role declares `package: crew`, so pi-subagents registers it as
`crew.<role>`; `name:` stays the bare local name. Dispatch `crew.reviewer`, not
`reviewer`. A bare `reviewer` or `researcher` resolves to pi-subagents' own
built-in agents. That is intended: pi-subagents' acceptance review and profiles
dispatch those bare names, and Crew no longer silently replaces them. The other
five bare names currently fall back to the unique local name (bare `lead`
reaches `crew.lead`), but that breaks as soon as any other source adds a
same-named agent, so dispatch the qualified name for every role.

To shadow a Crew role from a project overlay, the `.pi/agents/<role>.md` file
must also declare `package: crew`. Without it, the file registers as a separate
bare-named agent and the packaged `crew.<role>` stays in effect.

## 4. Project behavior and overlay

Pi reads the repo-root `AGENTS.md`. Canonical project skills live in
`.agents/skills/<name>/SKILL.md`; project roles live in `.pi/agents/<name>.md`.
Pi's skill namespace is flat and walks project scope before packages, so a local
same-named skill wins. Doctor reports the collision and both roots.

Run the installed validator by absolute Crew package path:

```sh
python3 /absolute/resolved/crew/root/scripts/check_skill_layout.py /absolute/consumer/repo
```

It catches missing role identity/description and forbidden runtime knobs as well
as invisible skill layouts.

## 5. Role posture and onboarding

Pi roles subtract from pi's default tool set rather than allowlisting:
`writes: none` renders `excludeTools: write, edit`, `writes: drafts` renders
`excludeTools: edit`, and `writes: full` excludes nothing. No role declares
`tools:`, because pi's `tools:` is a strict allowlist that would also shut out
ambient extensions. `lead` gets nested dispatch through
`allowNestedSubagents: true`. Every role retains `bash`, so file posture is
advisory unless the host permission system or sandbox enforces it. Dispatch
configuration owns model, reasoning depth, and turn budget.

MCP reaches a Pi subagent only through `mcp:` entries in its frontmatter, or
through ambient extensions such as the MCP adapter's proxy tool in a background
(`async`) run; a foreground child never loads ambient extensions. On every
harness the write posture limits dedicated file-write tools only: MCP side
effects are governed by the role's behaviour, not by `writes:`.

Ask **“onboard this project”** for a read-only audit. Applying findings requires a
separate explicit current-run authorization.
The supervising host verifies a fresh, non-persisted signal for that exact
invocation; saved, standing, reusable, and prior-run authority is rejected.
