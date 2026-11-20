# Scenarios: idea-shaping

## IS-1 One-line idea, empty slots

- **Prompt:** "Can you capture this as an idea?" + [one-line-idea](../fixtures/one-line-idea.md)
- **Slots:** empty
- **Mode:** Quick
- **Expected:** an idea card with every field present, gaps marked; at most three questions; a note that generic conventions were used and the draft path is the default.
- **Pass checklist**
  - [ ] Card header carries `kind: idea` and an empty `tracker-key:`.
  - [ ] Problem line names no solution ("skip button" appears only under Hunch).
  - [ ] At most three questions asked, and a draft produced anyway with its gaps marked.
  - [ ] Output says generic conventions were used and offers a proposed `planning-conventions` section or asks the operator about it.
  - [ ] Asks before creating `planning/drafts/`.

## IS-2 Detailed idea, filled slots

- **Prompt:** "Flesh this out for the pitch review." + [detailed-idea](../fixtures/detailed-idea.md)
- **Slots:** [Example Co planning-conventions](../fixtures/example-co/planning-conventions.md)
- **Mode:** Thorough
- **Expected:** a one-page why / what / how narrative (the slot's format), naming the riskiest assumption and the smallest version that tests it, costed in team-weeks, with the draft path under `product/drafts/`.
- **Pass checklist**
  - [ ] Uses the slot's narrative format, length limit and vocabulary (pitch, bet, cutoff).
  - [ ] Names the riskiest assumption and a smallest test of it, with what that test leaves untested.
  - [ ] Does not choose between alternative tests on the team's behalf.
  - [ ] Revenue risk and cutoff risk from the input appear as open questions or risks.
  - [ ] Says where the draft goes next (theme-portfolio or story-breakdown) only if the input gives a reason to.

## IS-3 Critique an existing card

- **Prompt:** "Is this idea card complete?" + the IS-1 output with Who set to "all users".
- **Slots:** empty
- **Mode:** Critique
- **Pass checklist**
  - [ ] Flags "all users", the missing success signal, and any solution-shaped problem.
  - [ ] Does not rewrite the card unless asked; if asked, writes a new file.

## IS-4 Mode override

- **Prompt:** "Just give me a quick card, no narrative." + [detailed-idea](../fixtures/detailed-idea.md)
- **Pass checklist**
  - [ ] Quick output despite the detailed input.

## IS-5 Empty narrative slot

- **Prompt:** "Write this up properly." + [detailed-idea](../fixtures/detailed-idea.md)
- **Slots:** empty
- **Mode:** Thorough
- **Pass checklist**
  - [ ] Narrative uses the problem / proposal / open questions shape and says generic conventions were used.
  - [ ] Each open question names who could answer it.
