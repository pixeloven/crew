# Packs

A **pack** is a sibling plugin that composes with Crew instead of competing with
it. Crew's core is agent behaviour — roles, planning, delegation, review. A domain,
a stack, or a craft lives in a pack beside it, installed from the same marketplace,
and plugs into Crew's roles through the slots Crew already has.

This page is the contract a pack meets. Crew never names a pack, and no pack is
privileged: the same rules apply to every one.

## The contract

1. **Name it `<domain>-skills`.** The name says what the pack covers, and the
   suffix says it carries skills only.
2. **Skills only — no roles.** A pack ships `skills/<name>/SKILL.md` and nothing
   under `roles/`, `agents/`, or `pi-agents/`. Crew's roles pick a pack's skills
   up from the harness's skill listing. A pack that needs a new persona is a
   signal the skill boundary is wrong. Second copies of Crew's methodology
   (planning, review, orchestration) collide or double-trigger beside Crew; put
   what is genuinely new in a skill, not a copy.
3. **Same schema, same gates.** Schema-v2 frontmatter (`name`, `description`,
   `tier`, `requires`, optional `expects-local`, optional `provides`), the
   directory-form layout, and the 110–300 character description policy with
   trigger language first. Run Crew's published checks — see below — rather than
   copying them; copies drift from the day they land.
4. **No project context baked in.** The dividing test is the one Crew uses on
   itself (see [Maintainers](MAINTAINERS.md)): any project must benefit from a
   pack skill. Anything bound to one deployment's vault, gateway, cluster, secret
   paths, or domains becomes a slot the skill defers to with `expects-local:`,
   and the consumer fills it. A concern Crew has no slot for becomes one the
   pack declares itself (see [Pack-owned slots](#pack-owned-slots)).
5. **Declare the Crew it needs — on every skill.** Each pack skill carries
   `plugin:crew@>=X.Y.Z` in its `requires:` (beside anything else it needs, e.g.
   `requires: [cli:gh, plugin:crew@>=X.Y.Z]`). Every skill, not some: a skill is
   listed, loaded, and moved on its own, so each one names the Crew it was checked
   against. `plugin:<name>@>=X.Y.Z` is part of the `requires` vocabulary; only `>=`
   on a full `X.Y.Z` is accepted. Pack mode fails each skill that omits it. Doctor
   compares it with the resolved Crew manifest and reports an unmet minimum as
   `DEGRADED`. Beyond the Crew dependency, `requires:` is rare: name sources in
   the skill body instead, so the skill degrades when one is missing (see
   [Capabilities](CAPABILITIES.md)).
6. **User-invoked utilities stay user-invoked.** Setup, scaffolding, and other
   one-shot skills should be invoked by the user where the harness allows it,
   so they do not trigger on ordinary work. Where a harness has no such switch,
   give the skill narrow trigger language instead.

## Filling a slot: `provides:`

Crew's roles cite local-skill **slots** (`roles/expected-local-skills.txt`), never
a concrete skill. A pack skill may fill one:

```yaml
---
name: example-conventions
description: Use when ...
tier: subject
requires: [plugin:crew@>=0.38.0]
provides: [platform-conventions]
---
```

`provides:` is a non-empty list; every entry must be a slot listed in Crew's
`roles/expected-local-skills.txt` or one the pack declares itself (see
[Pack-owned slots](#pack-owned-slots)). Crew itself fills no slots. Doctor reports
*"slot `platform-conventions` filled by pack `example-skills`"* next to local fills.

**`provides:` suits content that is generic by nature**, the same for every project
that installs the pack: a stack's conventions, a vendor's defaults. It does not suit
a per-project registry. A pack that knows common seams must not `provides:
[protected-seams]`: that would stand in for the project's own registry. It extends
the slot instead: its skills declare `expects-local: [protected-seams]`, and its
seam shapes become `▸ Fill` guidance that Onboarding seeds into the project's fill.

**Citing a slot in a skill body.** A skill that defers to a slot (`expects-local:`)
says so once, in one hedged sentence near the top — for example *"Where the
project has a `topology` local skill, its facts outrank anything below."* Do not
repeat the citation in every section: the one sentence covers the whole skill,
and each repetition costs body tokens on every load.

**A local overlay outranks a pack.** When both the consumer's overlay and a pack
fill a slot, the local skill is the fill of record. What "outranks" can mean
depends on the harness, and this is still an open question:

| Harness | What actually loads | What "outranks" means today |
|---|---|---|
| pi.dev | flat namespace; the nearest entry wins on a name collision | a same-named local skill shadows the pack copy; differently named ones both load |
| Claude Code | plugin skills are namespaced (`<plugin>:<name>`), project skills are bare | both copies load; nothing is shadowed |
| Codex | plugin skills are namespaced | both copies load; nothing is shadowed |

So on Claude Code and Codex, precedence is a convention, not a mechanism: the
project's `AGENTS.md` concern → local-skill map must point at the local skill,
and Doctor names both copies. Do not rely on collision behaviour to disable a
pack skill (the [README](../README.md) gives the same warning for Crew's own).
If a harness later grows a real precedence mechanism, this table changes.

## Pack-owned slots

Crew's slots name concerns every project has. A pack's domain often has its own —
the fields a tracker needs, the schema an event stream follows — that only that
pack's skills defer to. A pack declares those in `slots.txt` at its root, in the
same format as Crew's `roles/expected-local-skills.txt`: one name per line, `#`
comments and blank lines ignored.

```text
# example-skills: slots this pack's skills defer to.
tracker-fields
identity-event-schema
```

Each declared slot ships a starter stub at `templates/local-skills/<slot>.md`,
the file a consumer copies into its overlay and fills, exactly like Crew's stubs.
Mark its sections so Onboarding can fill it (see
[Packs ship stubs, not setup skills](#packs-ship-stubs-not-setup-skills)).
Once declared, the slot is valid in that pack's `expects-local:` and `provides:`:

```yaml
---
name: example-triage
description: Use when ...
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [tracker-fields, topology]
---
```

`check_skills.py --pack` fails the pack unless every entry in `slots.txt` is:

- **plain kebab-case**, and not prefixed with the pack's name — `tracker-fields`,
  never `example-skills:tracker-fields` or `example-skills-tracker-fields`. The
  consumer's fill is named `<project>-<slot>` by the same convention as Crew's;
- **unique** within the file;
- **not a Crew slot name** — neither a slot in `roles/expected-local-skills.txt`
  nor Crew's recommended vocabulary. Crew's names are reserved, so one slot name
  never means two contracts;
- **stubbed** at `templates/local-skills/<slot>.md`;
- **referenced** by at least one pack skill's `expects-local:`. A slot nothing
  defers to is a fill no skill reads.

A pack with no `slots.txt` declares none, and is checked exactly as before. Crew's
own run never reads a `slots.txt`, and a pack's slots never widen what another
pack is checked against: the check validates one pack alone, so it accepts only
Crew's slots and that pack's own.

**Uniqueness across packs.** Slot names share one namespace across every installed
pack. Pick names specific enough not to collide — `tracker-fields`, not `fields`.
If two installed packs declare the same name, Doctor reports the slot `DEGRADED`
and names both packs. It never guesses which pack owns the slot.

**How Doctor reports them.** Doctor adds each detected pack's slots to the
declared set, labelled with the owning pack — *"declared local slots: topology,
tracker-fields (pack `example-skills`)"*. An unfilled one is reported like Crew's,
as the pack's slot — *"pack `example-skills`'s slot `tracker-fields` is
unfilled"* — and the recommendation points at that pack's stub. Fills work exactly
as for Crew's slots: a local skill fills it by `provides:` or by the
`<project>-<slot>` name, another pack may `provides:` it, and a local overlay
outranks a pack. A pack whose `slots.txt` reuses a Crew slot name is also
`DEGRADED` in Doctor, for an install that never ran the check.

## Packs ship stubs, not setup skills

A pack's onboarding is its `templates/local-skills/` stubs. Crew's Onboarding
drives them for every installed pack. It reads the inventory, and for each
unfilled slot it proposes a local `<project>-<slot>` fill built from the owning
pack's stub. It audits by default, and applying needs a distinct authorization. Do
not ship a `<pack>-setup` skill: its description costs every session, and each
pack's setup would behave differently. Put that setup into the stub, and mark the
stub's sections so Onboarding knows who answers each one.

### Marking stub sections

A **section** is an ATX heading line (`#` to `######`) and every line after it, up
to the next heading of any level. Headings inside fenced code and the frontmatter
block do not count. A section still needs content while it contains `▸ Fill`.
Two markers, each alone on its own line inside a section, say how it gets filled:

| Marker | Meaning |
|---|---|
| `<!-- crew:discoverable capability=<cap> -->` | A tool can supply this section's facts. Onboarding hands the section to `learn`, which drafts it as a proposal with evidence; the operator promotes it. |
| `<!-- crew:optional -->` | The pack's skills can start without this section. **Quick** leaves it `▸ Fill`; **Thorough** asks it. |

```markdown
## Fields

<!-- crew:discoverable capability=mcp:tracker -->

> **▸ Fill:** each field, its type, and whether it is required.

## Escalation

<!-- crew:optional -->

> **▸ Fill:** where a blocked item goes.
```

The grammar is strict, so the split between sections is declared and never guessed:

- **One capability per marker. A section may carry several markers**, meaning
  any one of those sources can supply it. `learn` uses the first one the
  capability map shows as present, and the section stays a human question when
  none is. A capability may not repeat within a section.
  `<cap>` uses the `requires:` vocabulary: `mcp:<group>`, `cli:<tool>`,
  `external:github`, `external:web` or `cluster`. `plugin:` is not accepted,
  because a plugin is a dependency, not a source of facts. Use a name from
  [Capabilities](CAPABILITIES.md): an unlisted `mcp:` name gets a warning, not a
  failure.
- **Exact spelling.** No other attributes and no extra words. Anything else
  starting `<!-- crew:discoverable` or `<!-- crew:optional` is malformed.
- **Inside a section.** A marker before the first heading belongs to no section,
  and is an error.
- **Unmarked sections are human facts.** An unmarked section that contains
  `▸ Fill` becomes an interview question. Both markers can be on one section:
  Quick defers it, and Thorough hands it to `learn`.

`check_skills.py` checks this grammar in every stub under `templates/local-skills/`,
in pack mode and in Crew's own run.

**How Onboarding uses the markers.** `pack_slot_proposals` in
`scripts/onboarding_contract.py` returns one proposal per slot. Each proposal splits
the stub's unfilled sections into three lists: `discoverable_sections` (heading and
capability, handed to `learn`), `human_sections` (the interview) and
`deferred_sections` (optional ones that Quick leaves). A local fill that still
carries `▸ Fill` gets a `complete` proposal: re-run onboarding with Thorough to finish
it. A slot already filled by a pack gets no proposal, because a local fill would
outrank the pack, and that is a host decision. Doctor reports a fill that still
carries `▸ Fill` as `DEGRADED` (partial) and names the unfilled sections.

## Description cost is reported, never capped

Every listed skill's description is paid in every session; only the body is
lazy. The budget is the operator's to spend, but it should never be spent blind:

- `check_skills.py --report-cost` prints each skill's description size and the
  total. It never changes the exit code.
- Publish your pack's total in its README, in the required section below.
- Doctor sums what is installed (Crew plus every detected pack), compares it with
  known harness budgets, and names packs to disable when an operator wants
  headroom. Those budgets are dated measurements, not limits: Codex was measured
  on 2026-09-05 dividing one ~22 KB skills-listing budget across every entry
  (pixeloven/crew#72). Re-measure on a harness upgrade.

## Required README sections

### Description cost

Every pack README carries this section, in exactly this shape, so an operator can
add up packs' totals without reading prose:

````markdown
## Description cost

Measured with Crew's `check_skills.py --pack --report-cost` at Crew vX.Y.Z:

```text
<the report's per-skill lines, verbatim>
total always-on description chars: <N> (<M> skills)
```
````

The fenced block is the `--report-cost` output, verbatim and nothing else; its
last line is the figure of record. The reusable workflow writes this exact
section to the job summary on every run, and warns, without failing, when the
README's total line no longer matches. Update the section in any change that
edits a description.

### Install

Before a pack has a marketplace entry, its install section says so plainly and
gives what works today:

- **pi.dev:** the package from a `vX.Y.Z` tag, added beside Crew in `packages`;
  pi.dev has no marketplace, so nothing is pending there.
- **Claude Code:** load a local checkout with `claude --plugin-dir
  /absolute/path/to/<pack>`, or vendor `skills/` into the project.
- **Codex:** vendor `skills/` into `.agents/skills/`.
- Say the marketplace entry is pending, and print no `<pack>@<marketplace>`
  install command until the entry has merged — an install line that fails is
  worse than none.

Once the entry lands, replace the pending note with the plugin install line.
Either way, tell readers to install Crew first: a pack adds skills, not setup.

## Checks

### In CI: the reusable workflow

A pack's CI is one job calling Crew's reusable workflow:

```yaml
jobs:
  crew:
    uses: pixeloven/crew/.github/workflows/pack-checks.yml@vX.Y.Z
```

It checks the pack out at the workspace root and Crew under `.crew/`, runs
`check_skills.py --pack`, `check_skill_layout.py`, `check_links.py`, and
`check_versions.py` against the pack, and writes the `--report-cost` section to
the job summary. Both inputs are optional:

| Input | Default | Meaning |
|---|---|---|
| `crew-ref` | empty | the Crew ref whose scripts run. Empty resolves `v` + the highest `plugin:crew@>=` the pack's skills declare, falling back to `main` with a warning while that tag does not exist |
| `pack-root` | `.` | the pack's root, relative to the repository |

So by default the checks run with the vocabulary and slot list of the Crew the
pack says it needs; raise `requires:` to pick up newer checks. A pack **must not
vendor Crew's scripts, and must not check Crew out at its workspace root** — its
checks would then read Crew's own skills, links, and manifests as the pack's. The
workflow keeps Crew in a dot-directory no check scans. Add `.crew/` to the pack's
`.gitignore` so a local run never commits it.

### Bootstrap: before the Crew release is tagged

A new pack often needs a Crew that has merged but is not yet tagged. Until it is:

1. call the workflow at `@main`
   (`uses: pixeloven/crew/.github/workflows/pack-checks.yml@main`); the empty
   `crew-ref` already falls back to `main` and says so in a warning;
2. once Crew tags the release, pin the `uses:` line to `@vX.Y.Z` in the pack's
   next change. Nothing should track `main` after the tag exists.

### Locally

Run the checks from the **installed Crew root**, by absolute path, so the slot
list and vocabulary come from that Crew install and never from the pack:

```sh
CREW=/absolute/resolved/crew/root
PACK=/absolute/pack/repo
python3 "$CREW/scripts/check_skills.py" --root "$PACK" --pack --report-cost
python3 "$CREW/scripts/check_skill_layout.py" "$PACK"
python3 "$CREW/scripts/check_links.py" "$PACK"
python3 "$CREW/scripts/check_versions.py" "$PACK"
```

Pack mode differs from Crew's own run in four ways: a pack needs at least one
manifest (`.claude-plugin/plugin.json` and/or `package.json`) rather than both, it
must not ship `roles/`, `agents/`, or `pi-agents/`, every skill must declare
`plugin:crew@>=X.Y.Z`, and a `slots.txt` at the pack root is read and checked (see
[Pack-owned slots](#pack-owned-slots)). With no arguments the script still
validates Crew itself, exactly as before.

## Moving a skill from Crew to a pack

Moving a skill changes its namespaced name. Claude Code and Codex load plugin
skills as `<plugin>:<name>`, so `crew:<skill>` becomes `<pack>:<skill>`; pi.dev's
flat namespace keeps the bare name. Consumers install the pack beside Crew — the
skill no longer arrives with Crew — and update any `AGENTS.md` concern →
local-skill map, role overlay, or note that names `crew:<skill>`. Crew records
the move in its release notes and bumps its version as for any `skills/` change.
