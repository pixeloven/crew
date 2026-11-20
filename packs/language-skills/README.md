# language-skills

Language and toolchain conventions for coding agents: one skill per language,
Python first.

language-skills is a **pack** for [Crew](https://github.com/pixeloven/crew): a
sibling plugin that ships skills only, no roles, and plugs into Crew's roles
through the harness's skill listing. It meets Crew's
[pack contract](https://github.com/pixeloven/crew/blob/main/docs/PACKS.md) and is
checked by Crew's own published gates. Every skill declares
`requires: [plugin:crew@>=0.46.0]`.

Crew core keeps language-agnostic engineering practice. This pack holds what
depends on the language: the toolchain, the gates, the project shape.

## Design rule

**Portable practice in the skill; house choices in a slot.** Each skill states the
practice any project in that language benefits from, with a default toolchain it
names as a default. The frameworks and layout a project has actually chosen live in
that project's local skill, which outranks the pack. Framework names in a skill body
are examples of a choice, not the choice.

## Skills

| Skill | Use when | Slots |
|---|---|---|
| `python-conventions` | doing any Python work: packages, CLIs, MCP servers, agents, tests | `python-stack`, `agent-runtime` |

`python-conventions` is `tier: subject`. Its defaults are Python 3.12+, uv, Ruff
and pytest, and a uv workspace with one shared core and thin CLI and MCP surfaces.

## Slots

This pack declares one slot of its own in [`slots.txt`](slots.txt), with a starter
stub in [`templates/local-skills/`](templates/local-skills/). Fill it by copying the
stub into your overlay as `.agents/skills/<project>-python-stack/SKILL.md` and
replacing the `▸ Fill` blocks — or let Crew's `onboarding` drive it: sections marked
`<!-- crew:discoverable capability=cli:uv -->` can be drafted by Crew's `learn` from
`uv tree` and the project's `pyproject.toml` files.

| Slot | Holds | Read by |
|---|---|---|
| `python-stack` | the Python floor and toolchain, workspace layout, the framework chosen for each job (CLI, MCP, agents, console output), dev commands, house rules | `python-conventions` |

`python-conventions` also defers to Crew's `agent-runtime` slot for the exit-code
contract of autonomous runs. No skill fills a slot (`provides:`).

## Install

This pack lives in Crew's repo, under
[`packs/language-skills`](https://github.com/pixeloven/crew/tree/main/packs/language-skills), and ships on Crew's release
line. Install Crew first and follow its quickstarts; this pack adds skills, not
setup.

| Harness | How |
|---|---|
| Claude Code | `claude plugin install language-skills@pixeloven`, from the `pixeloven` marketplace (`pixeloven/crew`, pinned to a release tag) |
| OpenAI Codex | `codex plugin add language-skills@pixeloven`, from the same marketplace |
| pi.dev | the Crew package `git:github.com/pixeloven/crew@vX.Y.Z` carries this pack; a `skills` filter such as `["skills/**", "packs/language-skills/**"]` loads it beside Crew ([pi.dev quickstart](https://github.com/pixeloven/crew/blob/main/docs/quickstart-pi.md#enable-packs-per-project)) |

On Claude Code, install the pack at user scope, beside Crew, so it is available
machine-wide in every session:

```sh
claude plugin install language-skills@pixeloven --scope user
```

User scope is the CLI default and writes
`"enabledPlugins": { "language-skills@pixeloven": true }` to
`~/.claude/settings.json`. Each enabled pack adds its descriptions to the
always-on skill listing, and Claude Code collapses an over-budget listing to
names only, which hurts skill selection; the description cost below is the
price of keeping the pack on everywhere.

To enable the pack only in specific Python repos instead, run
`claude plugin install language-skills@pixeloven --scope project` from the project
root. This writes the same entry to the project's `.claude/settings.json`,
which you can also edit by hand and commit so the whole team gets it.
`--scope local` does the same in `.claude/settings.local.json` for you alone.
On pi.dev, the per-project form is an `autoload: false` delta on the Crew
package in the project's `.pi/settings.json` (same quickstart section). To try
a local checkout, run `claude --plugin-dir /absolute/path/to/crew/packs/language-skills`.

The pack lives at `packs/language-skills` in `pixeloven/crew` and installs as the
plugin `language-skills@pixeloven`. Its `package.json` names it `@pixeloven/language-skills`, but
it is not a pi package of its own: pi loads it through the Crew package. Before
Crew 0.67.0 the pack had its own repo,
[`pixeloven/language-skills`](https://github.com/pixeloven/language-skills); the fold imported it
at that repo's `main` head, and its earlier commit history stays there. The
plugin ID is unchanged. Nothing is published to a package registry — releases
are Crew's git tags.

As with Crew, Claude Code and Codex namespace plugin skills
(`language-skills:<name>`) while project skills stay bare, so a same-named local skill
does not shadow the pack copy. Do not rely on collision behaviour to disable a
pack skill.

## Description cost

Measured with Crew's `check_skills.py --pack --report-cost` at Crew v0.67.0:

```text
python-conventions  248
total always-on description chars: 248 (1 skills)
```

## Checks

Crew's CI checks this pack in its `packs` matrix job, with the scripts from the
same checkout. To run the same checks locally from a Crew checkout:

```sh
CREW=/absolute/path/to/crew
PACK="$CREW/packs/language-skills"
python3 "$CREW/scripts/check_skills.py" --pack --root "$PACK" --report-cost
python3 "$CREW/scripts/check_skill_layout.py" "$PACK"
python3 "$CREW/scripts/check_links.py" "$PACK"
python3 "$CREW/scripts/check_versions.py" "$PACK"
```

## Versioning

This pack carries Crew's version: `.claude-plugin/plugin.json` and
`package.json` match Crew's, and Crew's `vX.Y.Z` tag releases them together
([Versioning](https://github.com/pixeloven/crew/blob/main/docs/MAINTAINERS.md#versioning)). Bump Crew's
version in any change that touches this pack; Claude Code re-fetches a plugin
only when its version changes. From 0.67.0 the release notes are in
[Crew's CHANGELOG](https://github.com/pixeloven/crew/blob/main/CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
