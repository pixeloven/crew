---
name: theme-portfolio
description: Use when grouping planning items into themes for a cycle or roadmap review. Starts from the outcome and capacity, groups items into bets, writes each bet's case, checks the set fits, and slots new items into existing themes.
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [planning-conventions]
---

# Theme portfolio

A theme is a bet the team can explain in one breath: an outcome worth part of a
cycle, the items that go after it, and what it costs. Work from the outside in —
first what the cycle is for and what the team can spend, then which bets fit inside
that, and only then the case for each. Where the project has a
`planning-conventions` local skill, its cycle length, capacity unit, sizing scale
and narrative format outrank the defaults below.

## Depth modes

| Mode | Input looks like | Output |
|---|---|---|
| **Quick** | a flat list of items, or a new item and the existing themes | the budget, proposed groupings with a one-line rationale each, and orphans |
| **Thorough** | agreed groupings | a bet sheet per theme and the fit check for the whole set |
| **Critique** | an existing theme set | a challenge to each bet and to the set: categories posing as bets, cases that do not hold, a set that no longer fits |

Choose from the input; the operator can override. Show groupings for agreement
before writing bet sheets — a case built on the wrong grouping is wasted.

## 1. Start from the budget

Before grouping anything, pin down two things:

- **What the cycle is for.** The outcomes the planning group has been asked to move,
  if anyone has said. If not, ask once; if there is still no answer, carry on and
  list it as a gap — themes then have to justify themselves on their own.
- **What there is to spend.** Per team: capacity for the cycle, the share held back
  for maintenance and unplanned work, and what is left to plan with.

| Team | Capacity | Held back | Plannable |
|---|---|---|---|

Capacity nobody has given is asked for or listed as missing, never estimated.

## 2. Group into bets

- Group by **the outcome an item moves**, not by the team, the component or the
  requester. Two items that change the same user behaviour belong together even if
  different teams build them.
- Each bet names the measure it moves. A group that cannot name one is a category
  — a label for related work — not a bet; split it by outcome or fold its items
  into the bets they do move.
- An item that fits no bet is a finding, not a problem to hide: list it as an orphan
  and say whether it is a candidate bet, maintenance, or out of scope. Maintenance
  orphans still draw on the budget.
- **Slotting a new item** into existing themes: name the best fit and the runner-up,
  with one sentence each, and say what would change the answer.

## 3. Write each bet (Thorough)

```markdown
---
kind: theme
title: <outcome-led name>
stage:
tracker-key:
---

**Bet:** doing <items> will move <measure> from <today's value> to <target> by <when>.
**Why this cycle:** what changed or now hurts, with evidence.
**Cost:** each item with its size; the total in the capacity unit and its share of the budget.
**Guardrails:** at most two measures that must not get worse.
**Waits on:** other bets, teams or outside parties — and which item each one holds up.
**Could sink it:** at most three things, each with the team's response or "accepted".
```

If the slot names a narrative format, write **Bet** and **Why this cycle** in that
shape and keep the rest. **Why this cycle** must be news to somebody; if it only
restates what everyone already accepts, the bet has no reason to be in this cycle.

## 4. Check the fit

- **Demand against budget.** Convert every item to the capacity unit and sum it per
  team, including orphans that will be done anyway. Report team, plannable, demand
  and gap, and flag any team above 100% of plannable. Unsized items are listed, not
  guessed; [`story-breakdown`](../story-breakdown/SKILL.md) can size them.
- **Links between bets.** List every cross-bet and cross-team link as `A → B (why)`.
  Call out chains longer than two, cycles, and anything waiting on a party outside
  the planning group. A text list is enough; draw a diagram only when asked.
- **When it does not fit**, do not pick what goes. Offer two or three ways back under
  budget — defer a bet, thin one to its first item, move an item between teams — each
  with the outcome it gives up.

## Critique

Read an existing set against the same four steps, in order: is the budget still
true, is each theme a bet or a category, does each **Why this cycle** still hold,
and does the set still fit once anything added since is counted. Report by theme;
rewrite only if asked, into a new file.

## With no slot filled

Defaults: a quarter-length cycle, capacity in engineer-weeks with 20% held back, the
bet sheet above, drafts at `planning/drafts/theme-<slug>.md`. Say in the output that
these are defaults. Where the operator corrected one during the session — a real
cycle length, a real capacity unit — offer it back as a proposed
`planning-conventions` section for them to promote.
