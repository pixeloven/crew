---
name: example-co-planning-stages
description: Example Co's product planning stages and the readiness gate for entering each one, with must and should criteria. Load when judging whether a planning item is ready to move.
---

## Stages, in order

1. **Inbox** — captured, not yet looked at.
2. **Explore** — discovery: is the problem real and worth solving?
3. **Shape** — a direction is chosen and written up.
4. **Commit** — on a cycle's plan, sized and reviewed.
5. **Ship** — being built and rolled out.
6. **Learn** — results measured; keep, iterate or retire.

"Parked" is a tracker status, not a stage.

## Gate criteria per stage

| Stage | Criterion | must / should | How to tell it is met |
|---|---|---|---|
| Explore | Problem statement without a solution | must | the card's Problem line names no feature |
| Explore | Signal source cited | should | a link or quote in Signal |
| Shape | Evidence summary from Explore | must | a section citing at least two sources |
| Shape | Primary metric with baseline | must | metric, current value, target |
| Shape | More than one way to test the bet considered | should | listed in the narrative |
| Commit | Requirements doc Ready for every reader | must | requirements-review result attached |
| Commit | Cross-functional review recorded | must | review ledger attached, or "none needed" with reason |
| Commit | Sized in team-weeks | must | size on every epic |
| Ship | Rollout and rollback plan | must | section in the doc |
| Ship | Support briefed | should | note from the support lead role |
| Learn | Results against primary metric | must | a results note |

## Discovery-stage items

Items in Explore need: a hypothesis, the question, a timebox of at most three weeks,
and what result would end discovery. Commit-stage criteria do not apply.

## Item types that skip criteria

- **Supplier-mandated change** (a packaging or ingredient change a supplier requires)
  skips the primary-metric and ways-to-test criteria.
- **Recall follow-up** skips the evidence summary; the recall notice is its source.

## Review milestones

- **Cycle planning** (every six weeks): items should be at Commit. Run by the head of product role.
- **Monthly portfolio review**: every item in Shape is checked for staleness.
