---
name: readiness-gates
description: Use when asking whether product items are ready for their next planning stage or a review milestone. Checks each against every gate up to its target stage, lists the unmet musts with an owner and next action, and ranks a portfolio.
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [planning-stages]
---

# Readiness gates

Answer one question per item: **can it move to the stage it is aiming for, and if
not, what has to happen first, and who does it?** Where the project has a
`planning-stages` local skill, its stages and criteria outrank the generic gates
below.

## How a gate works

Each stage has a gate at its entrance. A gate holds a few criteria, and each
criterion is one of two kinds:

- a **must** holds the item back until it is met;
- a **should** is worth doing and gets reported, but never holds anything back.

To enter a stage, an item meets that stage's musts **and every must at the gates
before it**. Polish at a late stage does not make up for a gap at an early
one: an item headed for build with no agreed measure of success is not ready.

Judging each criterion:

- **Evidence or it is open.** A criterion is met only when you can point to the
  evidence. When the evidence is not in front of you, the must stays unmet and its
  next action is "show …" the missing piece.
- **Discovery is judged as discovery.** While the work is still learning whether
  the item deserves building, ask what it believes, what it is trying to learn,
  how long it has, and what result would settle it. Holding it to build criteria
  at that point only tells you it has not been built.
- **Only the slot grants skips.** An item may skip a criterion only when the
  `planning-stages` slot names its item type and that criterion; say which were
  skipped and why. With the slot empty, nothing is skipped.

The result for an item is its **list of unmet musts**, each with the role that can
close it and the next concrete action. An empty list means *ready*; never turn the
list into a score or a percentage.

## Depth modes

| Mode | Use when | Output per item |
|---|---|---|
| **Quick** | a check before a meeting, one item or many | ready / not ready and every unmet must, one line each with its owner role and next action |
| **Thorough** | the operator wants to get the item through | every criterion up to the target as met / open / unknown with its evidence, and a concrete fix for each one not met |
| **Critique** | criteria have been marked met elsewhere — a tracker field, a checklist, a previous run | a re-test of each claimed *met*: is the evidence actually there, does it say what the criterion asks, is it still current |

Pick from what was asked; the operator can override. Whenever there is more than one
item, add the portfolio table below, whatever the mode.

## Steps

1. **Establish the target.** Which stage is each item aiming for, or which review
   milestone is coming? If unstated, assume the stage after its current one.
2. **Gather evidence.** Use what the operator gave you: drafts from this pack, a
   requirements doc, pasted tracker items. If a tracker capability (`mcp:tracker`) is
   connected and the operator agrees, read the items from it; otherwise ask for an
   export or paste. Never block on a tool.
3. **Walk the gates** from the first stage up to the target, judging each criterion
   as above.
4. **Report** each item: verdict, unmet musts (owner role and next action),
   skipped criteria, then unmet shoulds in a separate list.

## Portfolio table

| Item | Now at | Aiming for | Unmet musts | Time at current stage | First next action |
|---|---|---|---|---|---|

Rank ready items first, then by fewest unmet musts, then by longest at the current
stage. Below the table, name any item that looks stuck: same stage and same unmet must
across reviews, when that history is available.

## Generic gates (used while the slot is empty)

| Entering | Must | Should |
|---|---|---|
| **Discovery** | problem statement; affected users named; the question discovery will answer | signal source cited |
| **Definition** | discovery evidence summarized; success metric with a baseline or a plan to get one; an owning team | more than one way to test the bet considered |
| **Ready to build** | requirements doc reviewed; scope and non-goals; cross-functional review done or "none needed" recorded; dependencies named; sized | risks with mitigations |
| **Launch** | acceptance criteria met; rollout and rollback plan; support and operations told | measurement in place |
| **Measure / close** | results against the success metric; the call recorded (keep, iterate, retire) | learnings shared |

Label every result checked this way as *generic gates*.

## Proposing the slot

Stages should come from the organisation, not from this table. When the slot is
empty:

- If a tracker is connected, its workflow states for planning items are the best
  source. Suggest the operator run crew's `learn` against it, which drafts the
  `planning-stages` **Stages** section as a proposal for them to promote.
- Otherwise, end the report with a proposed **Stages** and **Gate criteria** section,
  built from the stages the operator actually used in the conversation, marked as a
  draft for the operator to correct. Crew's `onboarding` can carry it into the slot.

Never present the generic gates as the organisation's.
