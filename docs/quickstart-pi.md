# Quickstart — pi.dev

On pi, Crew provides two things: its methodology skills, and its six roles as
readable files in `pi-agents/*.md`. Crew registers no agents and no tools on pi
and does not dispatch anything. Orchestration on pi (running a role as a
worker, in parallel or nested) is out of Crew's scope: a supervising host such
as [operator](https://github.com/pixeloven/operator) does it.

## 1. Install the package

Pin a published Crew release for reproducibility; replace `vX.Y.Z` with the
chosen tag:

```json
{
  "packages": [
    "git:github.com/pixeloven/crew@vX.Y.Z"
  ]
}
```

The package's `pi` manifest declares only `skills`: Crew's own `skills/` and,
since 0.67.0, the skills of each pack folded under `packs/<name>/`
(`infra-skills`, `planning-skills`, `identity-skills`, `language-skills`). pi
identifies a git package by its repository, so the packs cannot be separate
packages; a plain string entry like the one above loads Crew and every pack.
To load Crew alone, use the filter in the next section. The checkout also
carries `pi-agents/*.md` and the rest of the repo (`scripts/`, `templates/`)
that some skills run by absolute path. Read the
configured pin from settings and the resolved version from the checkout's
`.claude-plugin/plugin.json`. Do not use `git describe` for package version.

To use the skills without installing a package at all, see section 5.

### Enable packs per project

Pi lists every visible skill's description in full in every session, with no
budget, so each pack a project doesn't use is pure cost there. Install Crew
alone at user scope with a `skills` filter, in `~/.pi/agent/settings.json`:

```json
{
  "packages": [
    { "source": "git:github.com/pixeloven/crew@vX.Y.Z", "skills": ["skills/**"] }
  ]
}
```

Then add each pack to the project that uses it, in `.pi/settings.json`, as a
delta on that same package:

```json
{
  "packages": [
    {
      "source": "git:github.com/pixeloven/crew@vX.Y.Z",
      "autoload": false,
      "skills": ["packs/infra-skills/**"]
    }
  ]
}
```

The project then sees Crew plus that pack, loaded from your single user-scope
checkout. Keep `"autoload": false`: a project entry without it replaces the user
entry and needs its own checkout (`pi install … -l`), and loads nothing until
that runs. pi keys a package by its repository, not its ref, so the delta's tag
does not have to match. Filters only narrow what the manifest declares: a
plain string entry, or a filter that admits a pack, loads that pack everywhere
the entry applies. Another filter form loads Crew plus chosen packs in one
entry: `"skills": ["skills/**", "packs/infra-skills/**"]`. A `!` pattern
excludes, e.g. `"!packs/planning-skills/**"` or `"!skills/<name>"` for one skill.

To move to a new release, run `pi install git:github.com/pixeloven/crew@vNEW`.
It updates the entry in place and keeps its `skills` filter.

**Moving from separate pack packages (before 0.67.0).** Replace each
`git:github.com/pixeloven/<pack>@…` entry with the forms above: drop it from user
settings and, where a project used it, add the `autoload: false` delta naming
`packs/<pack>/**`. To keep every pack at user scope, as before, use one plain
`git:github.com/pixeloven/crew@vX.Y.Z` string entry.

## 2. Verify skill discovery

Start pi in the project and check that Crew's skills are listed. Crew adds no
agents and no tools on pi, so their absence is expected, not a failed install.

Do not substitute another harness's result for Pi runtime evidence. `pi -p` or
any prompt-mediated fresh-session probe is billed and requires explicit approval.

## 3. Roles as readable files

`pi-agents/<role>.md` holds each role (`lead`, `triage`, `investigator`,
`researcher`, `reviewer`, `implementer`), rendered from the same
`roles/<role>/` source as the Claude Code agents, so name, description, body
and intended posture match. Read a role to see how that work is done, or hand
the file to whatever runs your workers. Skills that describe dispatching a role
still name the roles; without a supervising host, do that work in the session.

The frontmatter is in the dialect pi agent runtimes read, for a host that
chooses to load the files:

- `name:` is the bare role name and `package: crew` namespaces it, so a runtime
  that honours `package` (such as pi-subagents) registers it as `crew.<role>`.
- Write posture subtracts from pi's default tool set: `writes: none` renders
  `excludeTools: write, edit`, `writes: drafts` renders `excludeTools: edit`,
  and `writes: full` excludes nothing. No role declares `tools:`, because pi's
  `tools:` is a strict allowlist that would also shut out ambient extensions.
- `lead` carries `allowNestedSubagents: true`, since it dispatches others.

Every role retains `bash`, so file posture is advisory unless the host
permission system or sandbox enforces it. Model, reasoning depth and turn
budget belong to whoever dispatches the role; the files never set them. On
every harness the write posture limits dedicated file-write tools only: MCP
side effects are governed by the role's behaviour, not by `writes:`.

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

Ask **“onboard this project”** for a read-only audit. Applying findings requires a
separate explicit current-run authorization.
The supervising host verifies a fresh, non-persisted signal for that exact
invocation; saved, standing, reusable, and prior-run authority is rejected.

## 5. Skills only, without a package

To use Crew's methodology without installing the package, load the skills on
each launch with `--skill`. Check out a release tag in full, because some
skills (`doctor`, `onboarding`, `learn`) run Crew's `scripts/` by absolute
path, and the roles stay readable in the checkout's `pi-agents/`:

```sh
git clone --depth 1 --branch vX.Y.Z https://github.com/pixeloven/crew /abs/crew
pi --skill /abs/crew/skills
```

One `--skill` pointing at the `skills/` directory loads every Crew skill. To
load a subset, pass each skill directory instead, repeating the flag:

```sh
pi --skill /abs/crew/skills/plan-generation --skill /abs/crew/skills/pr-review-checklist
```

`--no-skills` turns off pi's own skill discovery (project, user, and package
skills) but still loads every `--skill` path, so `pi --no-skills --skill
/abs/crew/skills` shows exactly Crew's skills.

The checked-out tag is the pin. To update, read the `### Consumer impact`
section of every [CHANGELOG](../CHANGELOG.md) release between your tag and the
new one, then check out the new tag.

How this was verified: on pi 0.87.1 and 1.4.0, with a fake model that reports
the skill names in the system prompt it receives, so no billed calls.
`--skill <crew>/skills` listed every skill in the tree (21 at 0.57.1). One skill
directory, or its `SKILL.md`, listed that one skill. Two `--skill` flags listed
both skills. `--no-skills --skill <crew>/skills` still listed all 21, and a run
with no `--skill` listed none.

## 6. Upgrading from a release that dispatched on pi

Crew 0.62.0 removed both pi dispatch paths: the experimental `crew_agent` tool
(and its `CREW_PI_AGENT`, `CREW_PI_DISPATCH` and `CREW_AGENT_TIMEOUT_SECONDS`
variables), and the `pi.subagents.agents` manifest entry with the
`pi-subagents` peer dependency. After the bump, `crew.<role>` agents no longer
appear and the variables do nothing; unset them. Keep `npm:pi-subagents` in your
`packages` only if you use it for your own agents. To run Crew's roles as
workers, use a supervising host such as operator.
