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

The marketplace entry is pending; until it merges, the plugin install line below
does not resolve. Install Crew first and follow its quickstarts — this pack adds
skills, not setup.

Once the marketplace entry lands, install the pack at user scope, beside Crew,
so it is available machine-wide in every session. Until then, the Claude Code
and Codex paths below are interim and load the pack per session or per project.

| Harness | How today |
|---|---|
| pi.dev | git package `git:github.com/pixeloven/language-skills@vX.Y.Z`, added beside Crew in `packages` (pi.dev has no marketplace) |
| Claude Code | interim: load a local checkout for one session with `claude --plugin-dir /absolute/path/to/language-skills`, or vendor `skills/` into the project |
| OpenAI Codex | interim: vendor `skills/` into the project's `.agents/skills/` |

Once the marketplace entry lands, install Crew (`crew@pixeloven`) first, then:

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
`claude plugin install language-skills@pixeloven --scope project` from the
project root. This writes the same entry to the project's
`.claude/settings.json`, which you can also edit by hand and commit so the
whole team gets it. `--scope local` does the same in
`.claude/settings.local.json` for you alone.

As with Crew, Claude Code and Codex namespace plugin skills
(`language-skills:<name>`) while project skills stay bare, so a same-named local
skill does not shadow the pack copy. Do not rely on collision behaviour to disable
a pack skill.

## Description cost

Measured with Crew's `check_skills.py --pack --report-cost` at Crew v0.50.0:

```text
python-conventions  248
total always-on description chars: 248 (1 skills)
```

## Checks

Run Crew's checks from the installed Crew root, by absolute path:

```sh
CREW=/absolute/resolved/crew/root
PACK=/absolute/path/to/language-skills
python3 "$CREW/scripts/check_skills.py" --pack --root "$PACK" --report-cost
python3 "$CREW/scripts/check_skill_layout.py" "$PACK"
python3 "$CREW/scripts/check_links.py" "$PACK"
python3 "$CREW/scripts/check_versions.py" "$PACK"
```

CI calls Crew's reusable `pack-checks.yml` workflow (see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Versioning

`.claude-plugin/plugin.json` and `package.json` carry the same version, and the
release tag is `vX.Y.Z` of that version. Bump it in any change that touches
`skills/` or `templates/`; Claude Code re-fetches a plugin only when its version
changes.

## License

MIT — see [LICENSE](LICENSE).
