# Scenarios: theme-portfolio

## TP-1 Group a flat list, filled slots

- **Prompt:** "Group these into bets for next cycle." + [theme-items](../fixtures/theme-items.md)
- **Slots:** [Example Co planning-conventions](../fixtures/example-co/planning-conventions.md)
- **Mode:** Quick
- **Expected:** the budget first (each team's capacity, 20% held back, plannable), then groupings by outcome (retention, acquisition, recipes), image hosting listed as an orphan / maintenance; asks for agreement before bet sheets.
- **Pass checklist**
  - [ ] Budget table comes before any grouping; asks once what outcomes the cycle is for, or lists that as a gap.
  - [ ] Groups by outcome, not by team.
  - [ ] Orphan named, not forced into a theme, and still counted against Platform's budget.
  - [ ] Uses "bet" vocabulary from the slot.
  - [ ] Stops for agreement before writing bet sheets.

## TP-2 Bet sheets and fit

- **Prompt:** "Agreed — write them up and check they fit." (continuing TP-1)
- **Mode:** Thorough
- **Pass checklist**
  - [ ] Each bet sheet has a **Bet** line with measure, today's value, target and when, written in the slot's why / what / how shape.
  - [ ] At most two guardrails and at most three "could sink it" items per bet.
  - [ ] Sizes converted with the slot's scale (XS 0.5 … XL 8).
  - [ ] Growth flagged over plannable (8 + 2 + 4 = 14 against 9.6).
  - [ ] Offers two or three ways back under budget, each with the outcome it gives up; does not choose one.
  - [ ] Links listed as `A → B (why)`.

## TP-3 Empty slots

- **Prompt:** "Group these into themes." + [theme-items](../fixtures/theme-items.md) with the capacity line removed
- **Slots:** empty
- **Pass checklist**
  - [ ] Output says defaults were used (quarter, engineer-weeks, 20% held back, the bet sheet).
  - [ ] Does not invent team capacity; asks or lists it as missing in the budget table.
  - [ ] Offers a proposed `planning-conventions` section for anything the operator corrects.

## TP-4 Slot a new item

- **Prompt:** "Where does 'Allergen filter' fit in our existing themes?" + TP-2's themes
- **Pass checklist**
  - [ ] Best fit and runner-up, one sentence each, and what would change the answer.

## TP-5 Critique an existing set

- **Prompt:** "Do these themes still hold up?" + TP-2's themes, plus a new theme "Platform work" holding image hosting and two new M items.
- **Mode:** Critique
- **Pass checklist**
  - [ ] Calls "Platform work" a category, not a bet (no outcome measure).
  - [ ] Re-runs the fit with the new items counted against Platform's plannable capacity.
  - [ ] Reports by theme; does not rewrite unless asked.
