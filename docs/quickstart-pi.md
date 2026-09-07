# Quickstart — pi.dev

## 1. Install a role-discoverable release

Pin a published Crew release for reproducibility; replace `vX.Y.Z` with the
chosen tag:

```json
{
  "packages": [
    "npm:pi-subagents@0.33.1",
    "git:github.com/pixeloven/crew@vX.Y.Z"
  ]
}
```

Crew must be `v0.35.0` or newer. Earlier rendered Pi roles omitted frontmatter
`name:`; pi-subagents silently drops such files. Read the configured pin from
settings and the resolved version from the checkout's
`.claude-plugin/plugin.json`. Do not use `git describe` for package version.
Package role discovery also requires `pi-subagents` `>=0.29.0`.

## 2. Verify runtime discovery

In the intended Pi runtime, run its native `/subagents-doctor`. It should list
the seven Crew roles (`lead`, `triage`, `investigator`, `researcher`, `responder`,
`reviewer`, `implementer`) and the package skill tree. Package skill and role
discovery are separate; report which half failed.

If skills appear but roles do not, inspect both the package's
`pi.subagents.agents` manifest entry and each role's `name:` frontmatter. These
are separate, historically observed silent-failure seams.

Do not substitute another harness's result for Pi runtime evidence. `pi -p` or
any prompt-mediated fresh-session probe is billed and requires explicit approval.

## 3. Project behavior and overlay

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

## 4. Role posture and onboarding

Pi role `tools:` is an allowlist, but every shipped role retains `bash`; file
posture is advisory unless the host permission system or sandbox enforces it.
Dispatch configuration owns model, reasoning depth, and turn budget.

Ask **“onboard this project”** for a read-only audit. Applying findings requires a
separate explicit current-run authorization.
