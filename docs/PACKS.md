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
   and the consumer fills it.
5. **Declare the Crew it needs.** Every pack declares
   `requires: [plugin:crew@>=X.Y.Z]` on the skills that depend on Crew's roles or
   slots. `plugin:<name>@>=X.Y.Z` is part of the `requires` vocabulary; only `>=`
   on a full `X.Y.Z` is accepted. Pack mode fails a pack that declares it nowhere.
   Doctor compares it with the resolved Crew manifest and reports an unmet
   minimum as `DEGRADED`.
6. **User-invoked utilities stay user-invoked.** Setup, scaffolding, and other
   one-shot skills should be invoked by the user where the harness allows it,
   so they do not trigger on ordinary work. Where a harness has no such switch,
   give the skill narrow trigger language instead.

## Filling a slot: `provides:`

Crew's roles cite local-skill **slots** (`roles/expected-local-skills.txt`), never
a concrete skill. A pack skill may fill one:

```yaml
---
name: example-seams
description: Use when ...
tier: subject
requires: [plugin:crew@>=0.38.0]
provides: [protected-seams]
---
```

`provides:` is a non-empty list; every entry must be a slot listed in Crew's
`roles/expected-local-skills.txt`. Crew itself fills no slots. Doctor reports
*"slot `protected-seams` filled by pack `example-skills`"* next to local fills.

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

## Description cost is reported, never capped

Every listed skill's description is paid in every session; only the body is
lazy. The budget is the operator's to spend, but it should never be spent blind:

- `check_skills.py --report-cost` prints each skill's description size and the
  total. It never changes the exit code.
- Publish your pack's total in its catalogue or README.
- Doctor sums what is installed (Crew plus every detected pack), compares it with
  known harness budgets, and names packs to disable when an operator wants
  headroom. Those budgets are dated measurements, not limits: Codex was measured
  on 2026-09-05 dividing one ~22 KB skills-listing budget across every entry
  (pixeloven/crew#72). Re-measure on a harness upgrade.

## Running Crew's checks from a pack

Run the checks from the **installed Crew root**, by absolute path, so the slot
list and vocabulary come from that Crew install and never from the pack:

```sh
CREW=/absolute/resolved/crew/root
python3 "$CREW/scripts/check_skills.py" --root /absolute/pack/repo --pack --report-cost
python3 "$CREW/scripts/check_skill_layout.py" /absolute/pack/repo
```

In CI, check out the Crew tag your pack's `requires:` names and run the same two
commands. Pack mode differs from Crew's own run in three ways: a pack needs at
least one manifest (`.claude-plugin/plugin.json` and/or `package.json`) rather
than both, it must not ship `roles/`, `agents/`, or `pi-agents/`, and it must
declare `plugin:crew@>=X.Y.Z`. With no arguments the script still validates Crew
itself, exactly as before.
