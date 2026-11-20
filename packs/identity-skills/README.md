# identity-skills

Vendor-neutral identity and authentication method for coding agents: auth seams,
surface map, flow tracing, funnel baselines, account investigation, risk
trends, and vendor-config review.

identity-skills is a **pack** for [Crew](https://github.com/pixeloven/crew): a
sibling plugin that ships skills only, no roles, and plugs into Crew's roles
through the harness's skill listing. It meets Crew's
[pack contract](https://github.com/pixeloven/crew/blob/main/docs/PACKS.md) and
is checked by Crew's own published gates. Every skill declares
`requires: [plugin:crew@>=0.45.0]` and nothing else.

## Design rule: adapt to any organisation, don't encode one

Every skill is **method plus discovery**. None presumes an organisation's
services, events, vendors or tools:

- Each skill works with its slots empty. It finds what it needs, and proposes
  slot content for the operator to commit (through Crew onboarding or `learn`).
  Slots are the *output* of discovery, not a prerequisite.
- Skills name capabilities, never providers. The investigation skills read the
  capability map in the project's `agent-runtime` fill and use whatever is there
  — a warehouse, product analytics, logs, a vendor admin API — or, with nothing,
  hand the operator exact queries and read back what is pasted. Every report says
  which sources it used and which were missing.
- Personal data and attack indicators are never recorded. The canonical rules
  live in `identity-ground-rules`; findings describe patterns, not values.

## Skills

| Skill | Use when |
|---|---|
| `identity-ground-rules` | Designing or reviewing auth, session or identity-data work; the canonical PII and indicator rules |
| `auth-seams` | A diff touches tokens, sessions, policy checks, claims, auth flows or trust boundaries |
| `identity-surface-map` | Asking where identity lives or who owns it; scoping or routing identity work |
| `auth-flow-tracing` | Explaining an auth flow across services or a vendor, or where it fails |
| `auth-funnel-signatures` | Building a funnel baseline, or telling an attack from a deploy or noise |
| `account-investigation` | Possible takeover, wrong-account attribution, a stuck sign-in or sign-up, or a few flagged accounts |
| `risk-signal-trends` | Aggregate abuse trends per signal family the organisation names, held against a comparison population |
| `identity-vendor-config` | Reviewing identity-vendor config as code, or checking whether live vendor state matches the code |

No skill fills a slot (`provides:`), and none names a vendor. Vendor-specific
skills are out of scope for v1.

## Slots

The skills defer organisation facts to local skills through `expects-local:`.

| Slot | Owner | Holds | Stub |
|---|---|---|---|
| `identity-surfaces` | this pack | the organisation's own classification dimensions; surfaces with location, who ships changes, how each touches identity, owner; vendors by role | [templates/local-skills/identity-surfaces.md](templates/local-skills/identity-surfaces.md) |
| `identity-event-schema` | this pack | event catalogue, identifiers, data flow, measured signal reliability, the signal families tracked, restricted fields, change/experiment-log pointer, query templates | [templates/local-skills/identity-event-schema.md](templates/local-skills/identity-event-schema.md) |
| `protected-seams` | Crew | the project's one seams registry; `auth-seams` extends it and ships [seed entries](skills/auth-seams/seed-seams.md) to copy in | Crew's stub |
| `agent-runtime` | Crew | the capability map the investigation skills adapt to | Crew's stub |

The pack's own slots are declared in [`slots.txt`](slots.txt). Copy a stub into
your overlay as `<project>-<slot>`, or let the matching skill propose its content.
Stubs mark sections a tool can discover with
`<!-- crew:discoverable capability=<cap> -->`. A slot is never a place for
secrets, personal data or attack indicators.

`auth-seams` deliberately does **not** `provides: [protected-seams]`: a project
keeps one registry with an approver behind it, and a pack fill would show that
slot as filled when no registry exists.

## Install

Install the pack at user scope, beside Crew, from the `pixeloven` marketplace,
so it is available machine-wide in every session. Install Crew
(`crew@pixeloven`) first.

| Harness | How |
|---|---|
| Claude Code | `claude plugin install identity-skills@pixeloven --scope user` |
| pi.dev | `pi install git:github.com/pixeloven/identity-skills@vX.Y.Z` |
| OpenAI Codex | `codex plugin marketplace add pixeloven/marketplace`, then `codex plugin add identity-skills@pixeloven` |

User scope is the CLI default and writes
`"enabledPlugins": { "identity-skills@pixeloven": true }` to
`~/.claude/settings.json`. Each enabled pack adds its descriptions to the
always-on skill listing, and Claude Code collapses an over-budget listing to
names only, which hurts skill selection; the description cost below is the
price of keeping the pack on everywhere.

pi installs globally by default, into `packages` in `~/.pi/agent/settings.json`;
add `-l` to install into the project's `.pi/settings.json` instead. Codex
records installed plugins in `~/.codex/config.toml`.

To enable the pack only in specific identity repos instead, run
`claude plugin install identity-skills@pixeloven --scope project` from the
project root. This writes the same entry to the project's
`.claude/settings.json`, which you can also edit by hand and commit so the
whole team gets it. `--scope local` does the same in
`.claude/settings.local.json` for you alone.

To try a local checkout instead, run `claude --plugin-dir /absolute/path/to/identity-skills`.

One identity, three spellings: the repo is `pixeloven/identity-skills`, the
package is `@pixeloven/identity-skills`, and the plugin installs as
`identity-skills@pixeloven`.
Nothing is published to a package registry — releases are git tags.

Install Crew first and follow its quickstarts; this pack adds skills, not setup.
Claude Code and Codex namespace plugin skills (`identity-skills:<name>`) while
project skills stay bare, so a same-named local skill does not shadow the pack
copy. Do not rely on collision behaviour to disable a pack skill.

## Description cost

Measured with Crew's `check_skills.py --pack --report-cost` at Crew v0.45.0:

```text
account-investigation   290
auth-flow-tracing       271
auth-funnel-signatures  267
auth-seams              263
identity-ground-rules   264
identity-surface-map    273
identity-vendor-config  296
risk-signal-trends      261
total always-on description chars: 2185 (8 skills)
```

## Tests

[`tests/`](tests/) holds scenario cases for every skill — trigger prompts, mode,
expected behaviour and a pass checklist — including an empty-slots run per skill,
negative triggers, and PII-discipline cases, all against the fictional Example
Co in [`tests/fixtures/example-co/`](tests/fixtures/example-co/).

## Checks

Run Crew's checks from the installed Crew root, by absolute path:

```sh
CREW=/absolute/resolved/crew/root
PACK=/absolute/path/to/identity-skills
python3 "$CREW/scripts/check_skills.py" --pack --root "$PACK" --report-cost
python3 "$CREW/scripts/check_skill_layout.py" "$PACK"
python3 "$CREW/scripts/check_links.py" "$PACK"
python3 "$CREW/scripts/check_versions.py" "$PACK"
```

CI calls Crew's reusable `pack-checks.yml` workflow (see `.github/workflows/ci.yml`).

## Versioning

`.claude-plugin/plugin.json` and `package.json` carry the same version, and the
release tag is `vX.Y.Z` of that version. Bump it in any change that touches
`skills/` or `templates/`; Claude Code re-fetches a plugin only when its version
changes.

## License

MIT — see [LICENSE](LICENSE).
