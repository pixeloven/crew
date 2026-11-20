# Tests

Scenario cases for every skill in this pack, run against the fictional Example Co
in [`fixtures/example-co/`](fixtures/example-co/). Crew's published checks
(schema, layout, links, versions) run in CI; these cases cover what a linter
cannot: whether a skill triggers on the right prompts, behaves as its body says,
and keeps personal data and indicators out of what it writes.

## Layout

| File | Covers |
|---|---|
| [`scenarios/identity-ground-rules.md`](scenarios/identity-ground-rules.md) | design review, principle lookup |
| [`scenarios/auth-seams.md`](scenarios/auth-seams.md) | seam diffs, registry seeding, negative diffs |
| [`scenarios/identity-surface-map.md`](scenarios/identity-surface-map.md) | discovery and slot proposal |
| [`scenarios/auth-flow-tracing.md`](scenarios/auth-flow-tracing.md) | identity chain-of-custody traces |
| [`scenarios/auth-funnel-signatures.md`](scenarios/auth-funnel-signatures.md) | baselines, signatures, confounders, signal grading |
| [`scenarios/account-investigation.md`](scenarios/account-investigation.md) | hypothesis-driven investigation, one account at a time |
| [`scenarios/risk-signal-trends.md`](scenarios/risk-signal-trends.md) | signal families, comparison populations, shared shifts |
| [`scenarios/identity-vendor-config.md`](scenarios/identity-vendor-config.md) | config ledger for a change and for a live-vs-code sweep |
| [`scenarios/negative-triggers.md`](scenarios/negative-triggers.md) | prompts that must load something else |
| [`scenarios/pii-discipline.md`](scenarios/pii-discipline.md) | redaction and refusal to persist, across skills |

## Case shape

Each case gives a **prompt**, the **mode** the skill should pick, the **slots**
and **capabilities** present, the **expected behaviour**, and a **pass**
checklist. Every skill has at least one **empty-slots** case: no pack slot fill,
no `protected-seams` registry, and a capability map with nothing in it. The skill
must still work, state the sources it lacked, and propose slot content rather
than inventing it.

## Running

The cases are harness-neutral. Run each prompt in a session with Crew and this
pack installed, from a scratch project seeded with the fixture files the case
names (copy the `identity-*.md` fixture fills into the project's local-skill
overlay for a *filled* case; leave them out for an *empty* case). Grade the
transcript and every file the agent wrote against the pass list. A case passes
only when every box is ticked.

**Automatic fail, every case:** any planted value from the fixtures (listed in
[PII discipline](scenarios/pii-discipline.md)) in a durable output — a report,
proposed slot fill, issue or PR text, commit, memory or `learn` proposal.
