# Scenarios: cross-functional-review

## CF-1 Who do we need, empty slots

- **Prompt:** "Who do we need to involve for this?" + [reshaping-brief](../fixtures/reshaping-brief.md)
- **Slots:** empty
- **Mode:** Quick (one agent reads through every lens)
- **Pass checklist**
  - [ ] All five default lenses listed, each with source *default* and *fired* or *quiet*.
  - [ ] Findings are phrased as facts about the concept, not as partner names.
  - [ ] security and privacy-legal each have at least one **Reshapes** finding, written out, and lead the roll-up.
  - [ ] The **Who to loop in** roll-up is derived from the findings: no partner appears without a finding behind them.
  - [ ] No subagents dispatched.
  - [ ] Suggests authoring lenses for partner functions the operator mentions.

## CF-2 Thorough, filled slots

- **Prompt:** "Do a full partner review before we design this." + [reshaping-brief](../fixtures/reshaping-brief.md)
- **Slots:** [Example Co review-lenses](../fixtures/example-co/review-lenses.md)
- **Mode:** Thorough
- **Expected lens set:** security (default), privacy-legal (slot, overrides default), data (default), accessibility (off — slot), operations-support (default), food-safety (slot, added).
- **Pass checklist**
  - [ ] Every lens shows its source; accessibility shown as *off (slot)* with its reason.
  - [ ] One crew reviewer dispatch per lens with anything to say, addressed by the harness's registered name (e.g. `crew.reviewer` on pi), each given only its own lens.
  - [ ] The dietary note produces a privacy-legal finding (health-adjacent data) and a food-safety finding (allergen claim), both **Reshapes**.
  - [ ] Review ledger has one row per finding, grouped Reshapes → Adds work → Covered, with each *By when* naming the decision the finding bears on (e.g. before the gift flow is designed), not a date read off the level.
  - [ ] *What they need from us* names the data inventory and the allergen-claim checklist, not "a meeting".
  - [ ] The roll-up is sorted by earliest by-when; partners are roles, never people.

## CF-3 No partners needed

- **Prompt:** "Does the print layout need any reviews?" + [covered-brief](../fixtures/covered-brief.md)
- **Slots:** Example Co review-lenses
- **Pass checklist**
  - [ ] Result is "No partners needed, because …", with accessibility *off (slot)* noted and no roll-up rows.

## CF-4 No subagent support

- **Prompt:** as CF-2, on a harness without subagent dispatch.
- **Pass checklist**
  - [ ] Runs lenses inline one at a time and says so.

## CF-5 Author a lens

- **Prompt:** "Help me write a lens for our payments-risk team."
- **Slots:** empty
- **Pass checklist**
  - [ ] Asks for the team's intake checklist or past review comments to draft from — not a walk through the stub headings.
  - [ ] Produces a lens with exactly two parts: *Questions this partner asks* and *Route* (a role and how to reach it).
  - [ ] Suggests the partner edit the draft; with no material given, says the questions have not been seen by the partner yet.
  - [ ] Delivers a `review-lenses` section for the operator to promote; writes nothing into the overlay.

## CF-6 Critique a ledger after the concept grew

- **Prompt:** "We reviewed this last month — is the ledger still right?" + the CF-2 ledger, and the reshaping brief with one line added: "Gift recipients can also set their own allergen preferences."
- **Slots:** Example Co review-lenses
- **Mode:** Critique
- **Pass checklist**
  - [ ] Names the new finding (recipients entering allergen data) and levels it, rather than re-running the whole review.
  - [ ] Flags any earlier finding whose level the change pushes up.
  - [ ] For each Reshapes finding, says whether the plan's scope or timeline reflects it yet.
  - [ ] Does not report sign-off status; points gate questions to readiness-gates.
