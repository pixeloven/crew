---
name: decision-records
description: Use when a change settles an architectural or hard-to-reverse choice, or when writing, reviewing or superseding an ADR. Covers when to record a decision, required content, and superseding.
tier: concept
requires: []
expects-local: [decision-record-format]
---

A decision record (an ADR) captures one choice, the reasons for it, and what it
costs, so the next agent or engineer does not re-litigate it or reverse it by
accident. Where the project has a `decision-record-format` local skill, its
template, location and numbering outrank anything below; this skill covers the
practice, not the house format.

## When to write one

Write a record when a change settles a choice that is expensive to reverse or that
someone will later ask "why did we do it this way?" about:

- an architecture, data-model, protocol or storage choice
- adopting, replacing or dropping a dependency, vendor, or platform service
- a security, privacy or access-boundary stance
- a convention every later change must follow
- deliberately *not* doing the obvious thing, where the reason isn't visible in the code

Do not write one for a reversible implementation detail, a bug fix, or a choice the
code and its tests already explain. A plan's phase choices belong in the plan; a
choice that outlives the plan belongs in a record.

Write it while the decision is being made, not afterwards: the alternatives and
their costs are known now and forgotten soon. A record can land in the same change
that implements the decision.

## Required content

Whatever the house format, a record is incomplete without:

1. **Context** — the problem and the forces on it: constraints, requirements, what
   made a decision necessary now.
2. **Decision** — the choice, stated as one unambiguous sentence before any
   elaboration.
3. **Alternatives considered** — each real option and why it lost. A record with no
   alternatives reads as a rationalisation.
4. **Consequences** — what gets easier, what gets harder, what is now ruled out, and
   any follow-up work it creates. Name the costs, not only the benefits.
5. **Status and date** — proposed, accepted, or superseded, and when.

Keep one decision per record. Link the issue, PR or plan it came from; do not copy
their content in.

## Superseding

An accepted record is history: do not rewrite its decision or reasoning when the
decision changes. Instead:

1. Write a new record that states the new decision and why the old one no longer
   holds.
2. Mark the old record `superseded by <new record>`, and have the new one name the
   record it supersedes. Links go both ways.
3. Leave the old record's body intact. Fixing a typo or a dead link is fine;
   changing what it decided is not.

A record that is wrong from the start, rather than outgrown, is still superseded,
not deleted: the mistake is part of the history.

## Reviewing a record

Check it against the required content above, and ask the load-bearing question:
*would someone reading only this record, a year from now, understand why the
obvious alternative was rejected?* If not, the alternatives or consequences are
missing. When a change contradicts an accepted record without superseding it,
flag that as a finding.
