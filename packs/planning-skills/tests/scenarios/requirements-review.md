# Scenarios: requirements-review

## RR-1 Reader verdicts, filled slots

- **Prompt:** "Check this PRD before review." + [weak-prd](../fixtures/weak-prd.md)
- **Slots:** [Example Co prd-bar](../fixtures/example-co/prd-bar.md), [planning-stages](../fixtures/example-co/planning-stages.md)
- **Mode:** Critique
- **Pass checklist**
  - [ ] Answers every slot check yes / no / not due, quoting the passage behind each yes.
  - [ ] Labels each reader Ready / Needs work / Missing; approver, operator and analyst are not Ready, so the doc is not ready for sign-off.
  - [ ] The overall verdict says who can act on the doc today and who cannot, with no averaged score.
  - [ ] Names foregone conclusion, unfalsifiable and launch-day surprise, each with its reader and the passage.
  - [ ] Names the local "cutoff blind spot" failure mode.
  - [ ] At most three coaching points, each naming the reader it unblocks and the next edit.

## RR-2 Refine Q&A, empty slots

- **Prompt:** "Help me fix the gaps in this PRD." + [weak-prd](../fixtures/weak-prd.md)
- **Slots:** empty
- **Mode:** Thorough
- **Pass checklist**
  - [ ] Starts with the reader furthest from Ready (the approver: no problem, no evidence), one or two questions at a time, offering candidate answers.
  - [ ] Writes a **new** file (e.g. `weak-prd.v2.md`); the source is unchanged.
  - [ ] Lists what changed at the top of the new file.
  - [ ] Labels the result *generic checks* and asks whether the org has a template, offering a proposed `prd-bar` section.

## RR-3 Prompts for an early draft

- **Prompt:** "I need to write a PRD for the skip feature. Where do I start?" + [detailed-idea](../fixtures/detailed-idea.md)
- **Mode:** Quick
- **Pass checklist**
  - [ ] Questions grouped by the reader who will ask them, in answer order, and the sections to start from (the slot's sections when filled).
  - [ ] No verdicts.

## RR-4 Stage awareness

- **Prompt:** "Review this doc" + an Explore-stage item's discovery brief
- **Slots:** Example Co planning-stages + prd-bar
- **Pass checklist**
  - [ ] Judged on the question and evidence so far; the warehouse-cutoff and metric checks are *not due* (due only from Shape), so the operator and analyst are not marked Missing.
