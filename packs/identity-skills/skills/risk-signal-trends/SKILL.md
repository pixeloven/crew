---
name: risk-signal-trends
description: Use when asked for abuse or fraud trends in sign-in, challenge or recovery traffic, or a risky-traffic report. Aggregate only, per signal family the organisation names; compares a segment with a comparison population and separates abuse from a shift both share.
tier: concept
requires: [plugin:crew@>=0.45.0]
expects-local: [identity-event-schema, agent-runtime]
---

# Risk signal trends

Answers one kind of question: *is this abuse pattern growing, shrinking or
steady, and is the movement really abuse?* Every answer is an aggregate. The
skill never names, lists or ranks accounts; where a finding deserves a closer
look, it suggests investigating a small sample from the segment (see *Output*).

Nothing here presumes which abuse matters. Where the project has an
`identity-event-schema` local skill, its signal families, reliability grades and
change-log pointer come first; with it empty, `auth-funnel-signatures` discovers
the events and the operator names the families. Read the capability map in the
project's `agent-runtime` fill and use whatever store it lists; with none, hand
the operator each query and read back the pasted aggregate.

`identity-ground-rules` governs everything here. No indicator value ever reaches
a report, the query appendix or memory.

## Signal families

A **signal family** is one abuse pattern this organisation cares about, written
as: a name, the funnel steps or `auth-funnel-signatures` shapes that evidence it,
and the signals that count toward it. Take the families from the
`identity-event-schema` fill. With none recorded, show the operator the shapes
the funnel can actually evidence, ask which they track and what each is called
internally, and propose the family rows. Never assume a family the operator has
not confirmed, and never report one the events cannot evidence — say which
family is unmeasurable and what event would make it measurable.

## Two populations

Every trend is a difference between two populations, so name both before
measuring anything:

- the **segment** — the traffic the family is about. Draw it **by shape**
  (sessions matching the family's pattern, for example three or more challenges
  issued and none passed; write the predicate in the appendix), or **by operator
  predicate** (a filter naming infrastructure or values: use it only in the live
  query; everywhere else it is `<operator-supplied segment predicate>` and the
  segment is *segment S*);
- the **comparison population** — what the segment is held against: all other
  sessions in the same window by default, or a population the operator knows to
  be clean. Say which, and why it is comparable.

Measure both over the current window and the comparison window, each step
divided by funnel entries for that population (`auth-funnel-signatures` §3).

## Shared shifts

Before calling a movement abuse, look at the comparison population. If it
moved too — the same way, and by about as much — the change is a **shared
shift**, not a signal: something common to all traffic changed — a release, a
configuration change, how events are counted — and the family is not the story. Name the candidate from the change
log and the instrumentation checks (`auth-funnel-signatures` §5) and stop
attributing.

Only a movement confined to the segment goes on to those confounder checks as a
possible abuse finding.

## Trend findings

Per family, one finding:

- **direction and size** — the segment's rate in each window, the comparison
  population's, and the change against normal variation;
- **classification** — *likely abuse*, *shared shift* (with the candidate
  cause), *noise*, or *unmeasurable* (with the missing event);
- **confidence**, and the signals relied on with their grades;
- **breadth**, as counts only: how many accounts in the segment show one, two,
  or three or more **independent** signals from the family (different events or
  stores, not two fields of one event).

## Output

Markdown findings in Crew's reporting-contract order: per family, the finding
above and the confounders checked. Then **Sources** used and missing, and an
**Appendix: queries** with placeholders for any operator predicate.

Where a *likely abuse* finding warrants a closer look, end it with a suggestion:
*investigate a sample of N accounts from segment S* through
`account-investigation`, with N set by the operator or, by default, 5. The
suggestion names the segment and the size, never the accounts. When a sample has
been investigated, record the outcome against the signals used, so their grades
can be revisited.

## Depth

| Mode | When | Output |
|---|---|---|
| Quick | "anything unusual this week?" | one family, both populations, shared-shift check, classification |
| Thorough | a suspected campaign or a recurring report | every named family, confounder checks, breadth counts |
| Critique | an existing trend report | no comparison population, unnormalised rates, shared shifts called abuse, account IDs or leaked values in an aggregate report |

## Never

- call a movement abuse when the comparison population moved with it;
- name, list or rank accounts — aggregates only;
- persist a segment predicate or any indicator outside the live query.
