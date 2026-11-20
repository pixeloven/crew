# Scenarios: readiness-gates

## RG-1 Portfolio, filled slots

- **Prompt:** "Which of these are ready for cycle planning?" + three drafts: the IS-2 narrative, the [weak PRD](../fixtures/weak-prd.md), and a supplier-mandated item ("Switch to the insulated liner our packaging supplier now requires", sized M, no metric).
- **Slots:** [Example Co planning-stages](../fixtures/example-co/planning-stages.md)
- **Mode:** Quick (portfolio table added because there are several items)
- **Expected:** each checked against Commit, cumulatively (Explore + Shape + Commit musts); portfolio table ranked ready first, then fewest unmet musts, then longest at current stage.
- **Pass checklist**
  - [ ] Each item shows its unmet musts, each with an owner role and a next action; no percentage or score.
  - [ ] Weak PRD keeps the Explore problem-statement must unmet even though it targets Commit.
  - [ ] Supplier-mandated item skips only the metric and ways-to-test criteria, and says so.
  - [ ] Unmet shoulds listed separately and never hold an item back.
  - [ ] Missing evidence leaves the must unmet with a "show …" next action, not assumed met.

## RG-2 Single item, empty slots

- **Prompt:** "Is this ready to build?" + [detailed-idea](../fixtures/detailed-idea.md)
- **Slots:** empty
- **Mode:** Quick
- **Expected:** not ready, with every unmet must on the generic gates, each with an owner role and next action.
- **Pass checklist**
  - [ ] Result labelled *generic gates*.
  - [ ] Not ready: no reviewed requirements doc, no cross-functional review recorded.
  - [ ] Proposes deriving stages from the tracker workflow via crew `learn`, or offers a draft **Stages** section built from the conversation.
  - [ ] Never claims the generic stages are the organisation's.

## RG-3 Discovery item

- **Prompt:** "Can this exit discovery?" + an Explore-stage item with hypothesis, question and a two-week timebox but no result yet.
- **Slots:** Example Co planning-stages
- **Mode:** Thorough
- **Pass checklist**
  - [ ] Checked on discovery criteria only.
  - [ ] Unmet: the result that ends discovery; fix names what evidence to gather.

## RG-4 No tracker connection

- **Prompt:** "Check everything in our tracker's Shape column."
- **Slots:** Example Co planning-stages; no tracker capability connected.
- **Pass checklist**
  - [ ] Asks for an export or paste instead of failing.

## RG-5 Critique claimed evidence

- **Prompt:** "The tracker says these two are ready for Commit — are they?" + two pulled items whose tracker fields mark every Commit criterion met; one links a requirements-review result from before the scope changed, the other has a metric field reading "TBD".
- **Slots:** Example Co planning-stages
- **Mode:** Critique
- **Pass checklist**
  - [ ] Re-tests each criterion marked met rather than accepting the field.
  - [ ] Reopens the requirements-doc must as out of date, with a "show …" next action.
  - [ ] Reopens the metric must: "TBD" is not a baseline and target.
  - [ ] Still produces the portfolio table.
