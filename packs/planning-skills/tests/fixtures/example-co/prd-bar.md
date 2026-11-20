---
name: example-co-prd-bar
description: Example Co's bar for product requirements docs — reader checks, required sections, template location and local failure modes. Load when checking or refining a PRD.
---

## Reader checks

| Reader | Check (a yes/no question) | Due from stage |
|---|---|---|
| Approver | Does the problem name the subscriber segment and the moment it hurts? | |
| Approver | Is there contact-reason data, survey or experiment evidence, with dates? | |
| Builder | Are there in, out and later lists? | Shape |
| Operator | Does it state the effect on the warehouse cutoff and on delivery? | Shape |
| Operator | Does each risk have an owning role and a mitigation? | Shape |
| Analyst | Is there one primary metric with baseline, target and the dashboard it lives on? | Shape |

## Required sections

Problem · Evidence · Users · Metric · Scope (in / out / later) · Ops impact · Risks · Open questions.
Ops impact is required from Shape onward.

## Template

`docs/templates/requirements.md` in the product repository. New docs start from it.

## Local failure modes

- **The cutoff blind spot** (operator) — a change to what subscribers can do near
  the weekly order cutoff with no word on the warehouse.
- **The one-market doc** (builder, operator) — assumes the largest market's delivery
  rules everywhere.

## Verdict labels

Ready / Needs work / Missing. Ready for sign-off = every reader Ready on the checks due at the item's stage.
