# planning-skills

Product planning skills for coding agents: take a raw signal to a shaped idea, a
reviewed requirements doc, a cross-functional risk check, and a sized backlog.

planning-skills is a **pack** for [Crew](https://github.com/pixeloven/crew): a
sibling plugin that ships skills only, no roles, and plugs into Crew's roles
through the harness's skill listing. It meets Crew's
[pack contract](https://github.com/pixeloven/crew/blob/main/docs/PACKS.md) and is
checked by Crew's own published gates. Every skill declares
`requires: [plugin:crew@>=0.45.0]`.

Crew's `plan-*` skills plan *agent work*. This pack plans *what a team builds and
why*. No skill here is named `plan-*`, and `story-breakdown` names the boundary in
its description.

## Design rule

**Adapt to any organisation; encode none.** Each skill is a method plus discovery:

- it works with every slot empty, on generic defaults it labels as such;
- it names capabilities (`mcp:tracker`, `mcp:docs`) and never hard-requires a tool —
  without one it asks for a paste or export, or hands the operator a file;
- it proposes slot content from what the operator said, rather than assuming it.

Core skills only **draft** Markdown. `tracker-sync` is the one skill that writes
outside the repository, only when asked, and only after showing every field.
Reporting, chunk-and-pause, batch review and confirm-before-write come from Crew's
reporting contract and are not restated here.

## Skills

| Skill | Use when | Slots |
|---|---|---|
| `idea-shaping` | an idea or problem worth writing down needs to become a card the team can discuss, or a card needs a narrative | `planning-conventions` |
| `readiness-gates` | asking whether items are ready for their next stage or a review milestone | `planning-stages` |
| `theme-portfolio` | grouping items into themes for a cycle or roadmap review, starting from the outcome and capacity | `planning-conventions` |
| `story-breakdown` | breaking a mature item or requirements doc into epics and stories with acceptance criteria | `planning-conventions` |
| `requirements-review` | checking a requirements doc reader by reader, coaching it, or refining it | `prd-bar`, `planning-stages` |
| `cross-functional-review` | logging which partner functions a concept needs, how early, and why; authoring lenses | `review-lenses` |
| `tracker-sync` | pushing drafts to an issue tracker or pulling items into drafts (user-invoked) | `tracker-fields` |

Every skill offers three depth modes, chosen from the maturity of the input; the
operator can override:

- **Quick** — the smallest useful result: a card, a skeleton, a roll-up, a dry run;
- **Thorough** — the full artifact, built out with the operator;
- **Critique** — a sceptical read of an artifact that already exists.

Each skill's own table says what the three mean for it. `cross-functional-review`
in Thorough dispatches one Crew `reviewer` per lens.

All seven are `tier: subject`: they carry product-planning craft, not agent
behaviour, and no role needs them to function.

## Planning moments

Which skill to reach for, in the order work usually flows:

| Moment | Skill, mode |
|---|---|
| A customer quote or a hallway idea arrives | `idea-shaping`, Quick |
| An idea is worth a pitch | `idea-shaping`, Thorough; then `cross-functional-review`, Quick |
| Writing the requirements doc | `requirements-review`, Quick (prompts), then Thorough (refine) |
| Before the doc goes to reviewers | `requirements-review`, Critique; `cross-functional-review`, Thorough |
| Cycle or roadmap planning | `theme-portfolio`, Quick → Thorough; `readiness-gates`, Quick |
| Committed item heads to a team | `story-breakdown`, Quick → Thorough |
| Drafts need to be in the tracker | `tracker-sync`, Quick (dry run) → Thorough |
| Scoring what is already in the tracker | `tracker-sync` pull, then `readiness-gates`, Critique |

## Slots

This pack declares five slots of its own in [`slots.txt`](slots.txt), each with a
starter stub in [`templates/local-skills/`](templates/local-skills/). Fill one by
copying its stub into your overlay as `.agents/skills/<project>-<slot>/SKILL.md`
and replacing the `▸ Fill` blocks — or let Crew's `onboarding` drive it: sections
marked `<!-- crew:discoverable capability=… -->` can be drafted by Crew's `learn`
from a connected tool, and the rest is a short interview.

| Slot | Holds | Read by |
|---|---|---|
| `planning-stages` | ordered stages; what each stage's gate adds, each criterion a must or a should; discovery-stage criteria; item types that skip criteria; review milestones | `readiness-gates`, `requirements-review` |
| `prd-bar` | the readers a doc must serve and a yes/no check list for each; required sections; template location; local failure modes; verdict labels | `requirements-review` |
| `review-lenses` | one section per lens: the questions that partner asks of a concept, and the route to the role that answers. Overrides, adds to, or switches off (`n/a`) the five defaults | `cross-functional-review` |
| `planning-conventions` | cycle length, capacity unit, sizing scale, item hierarchy, draft location, narrative format | `idea-shaping`, `theme-portfolio`, `story-breakdown` |
| `tracker-fields` | tracker kind, identifiers, issue types, field map (our name, the tracker's name, how to write a value), link types, write policy | `tracker-sync` |

No skill fills a Crew slot (`provides:`).

## Install

| Harness | How |
|---|---|
| Claude Code | plugin `planning-skills@pixeloven`, beside `crew@pixeloven`; for a local checkout: `claude --plugin-dir /absolute/path/to/planning-skills` |
| pi.dev | git package `git:github.com/pixeloven/planning-skills@vX.Y.Z`, added beside Crew in the project's `packages` (pi.dev has no marketplace) |
| OpenAI Codex | vendor `skills/` into `.agents/skills/` |

Install the pack at user scope, beside Crew, so it is available machine-wide
in every session. Install Crew (`crew@pixeloven`) first, then:

```sh
claude plugin install planning-skills@pixeloven --scope user
```

User scope is the CLI default and writes
`"enabledPlugins": { "planning-skills@pixeloven": true }` to
`~/.claude/settings.json`. Each enabled pack adds its descriptions to the
always-on skill listing, and Claude Code collapses an over-budget listing to
names only, which hurts skill selection; the description cost below is the
price of keeping the pack on everywhere.

To enable the pack only in the projects where product planning happens instead,
run `claude plugin install planning-skills@pixeloven --scope project` from the
project root. This writes the same entry to the project's
`.claude/settings.json`, which you can also edit by hand and commit so the whole
team gets it. `--scope local` does the same in `.claude/settings.local.json` for
you alone.

Follow Crew's quickstarts; this pack adds skills, not setup. As with Crew,
Claude Code and Codex namespace plugin skills
(`planning-skills:<name>`) while project skills stay bare, so a same-named local
skill does not shadow the pack copy. Do not rely on collision behaviour to disable
a pack skill.

## Description cost

Measured with Crew's `check_skills.py --pack --report-cost` at Crew v0.45.0:

```text
cross-functional-review  241
idea-shaping             195
readiness-gates          231
requirements-review      217
story-breakdown          221
theme-portfolio          224
tracker-sync             257
total always-on description chars: 1586 (7 skills)
```

## Checks

Run Crew's checks from the installed Crew root, by absolute path:

```sh
CREW=/absolute/resolved/crew/root
PACK=/absolute/path/to/planning-skills
python3 "$CREW/scripts/check_skills.py" --pack --root "$PACK" --report-cost
python3 "$CREW/scripts/check_skill_layout.py" "$PACK"
python3 "$CREW/scripts/check_links.py" "$PACK"
python3 "$CREW/scripts/check_versions.py" "$PACK"
```

CI calls Crew's reusable `pack-checks.yml` workflow (see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

## Tests

[`tests/`](tests/) holds scenario cases per skill — trigger prompt, fixture, slot
state, mode, expected behaviour and a pass checklist — including an empty-slots run
for every skill and negative triggers, plus filled slots for a fictional "Example Co".
They are graded by hand or by an agent harness; see [`tests/README.md`](tests/README.md).

## Versioning

`.claude-plugin/plugin.json` and `package.json` carry the same version, and the
release tag is `vX.Y.Z` of that version. Bump it in any change that touches
`skills/` or `templates/`; Claude Code re-fetches a plugin only when its version
changes.

## License

MIT — see [LICENSE](LICENSE).
