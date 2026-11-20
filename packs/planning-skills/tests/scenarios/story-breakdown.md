# Scenarios: story-breakdown

## SB-1 Skeleton, filled slots

- **Prompt:** "Break the skip feature into pitches and slices for the Subscriptions backlog." + the IS-2 narrative
- **Slots:** [Example Co planning-conventions](../fixtures/example-co/planning-conventions.md)
- **Mode:** Quick
- **Pass checklist**
  - [ ] Uses "pitch" and "slice" from the slot.
  - [ ] Epics are slices of user value, not layers (no "Skip API" epic).
  - [ ] First epic ships something a subscriber can touch.
  - [ ] Each epic says what it leaves out.

## SB-2 Stories with criteria

- **Prompt:** "Now write the slices." (continuing SB-1)
- **Mode:** Thorough
- **Pass checklist**
  - [ ] Every story has `kind: story`, `parent:`, `size:` on the XS–XL scale, empty `tracker-key:`.
  - [ ] Acceptance criteria are Given / When / Then, observable, one behaviour each.
  - [ ] Includes the after-cutoff edge case.
  - [ ] No criterion names a table, endpoint or framework.
  - [ ] An XL item is split or flagged for splitting.

## SB-3 Empty slots

- **Prompt:** "Turn this into epics and stories." + the IS-2 narrative
- **Slots:** empty
- **Pass checklist**
  - [ ] Defaults stated: epic → story, T-shirt sizes, `planning/drafts/<epic-slug>/`.
  - [ ] Offers sizing and hierarchy back as a proposed `planning-conventions` section, or suggests crew `learn` against a connected tracker.

## SB-4 Discovery item

- **Prompt:** "Break down the allergen filter." + an Explore-stage item
- **Pass checklist**
  - [ ] Produces timeboxed knowledge stories (question, method, timebox, evidence), not build stories.

## SB-5 Critique

- **Prompt:** "Critique these stories." + three stories, one with seven criteria and one with "and also".
- **Pass checklist**
  - [ ] Flags the over-long story for splitting and the compound criterion.

## SB-N Negative triggers

| Prompt | Must not happen |
|---|---|
| "Plan the refactor of module X." | story-breakdown loads |
| "Break the database migration into phases for the agents." | story-breakdown loads |
| "Write acceptance tests for the cart service." | story-breakdown loads |

If story-breakdown does load on a borderline prompt, it must name the boundary (crew `plan-generation`) and stop.
