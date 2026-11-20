---
name: story-breakdown
description: Use when breaking a mature product item or requirements doc into epics and stories for a team backlog. Writes testable acceptance criteria, relative sizes and dependencies. Not for agent work plans (crew plan-generation).
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [planning-conventions]
---

# Story breakdown

Turn a product item that is ready for build — a reviewed requirements doc, a
developed idea, a theme's committed item — into epics and stories a team can pull
into a backlog. Where the project has a `planning-conventions` local skill, its
hierarchy names and sizing scale outrank the defaults below.

**Boundary.** This skill plans *what a product team builds for its users*. Planning
how an agent will carry out a task — phases, delegation, validation gates for a
refactor or a migration — is crew's `plan-generation`, not this. If the request is
about a code change rather than a product outcome, say so and stop.

## Depth modes

| Mode | Input looks like | Output |
|---|---|---|
| **Quick** | a doc or item, first pass | an epic skeleton: epic titles, one-line goals, what each leaves out |
| **Thorough** | an agreed skeleton | stories with acceptance criteria, sizes and dependencies |
| **Critique** | an existing backlog slice | a story-by-story check of criteria, sizes, splits and missing stories |

Choose from the input; the operator can override. Get the skeleton agreed before
writing stories under it.

## Epics

- One epic per **releasable slice of user value**, not per layer or component.
  "Buyers can reorder from their history" is an epic; "Reorder API" is not.
- Order epics so the first one ships something a user can touch, however thin.
- Each epic states what it deliberately leaves out.

## Stories

```markdown
---
kind: story
title: <user-visible change, verb first>
parent: <epic title or tracker-key>
size: <on the project's scale>
tracker-key:
---

As a <specific user>, I want <capability> so that <outcome>.

**Acceptance criteria**
- Given <context>, when <action>, then <observable result>.
- ...

**Depends on:** <story or external item, and why>
**Notes:** design links, open questions.
```

Acceptance criteria are the part this pack owns, so hold them to a bar:

- **Observable.** Each names something a tester or a user can see, not an internal
  step ("then the order appears in the history list", not "then the service saves it").
- **Testable alone.** One behaviour per criterion; no "and also".
- **Edges included.** Empty, error, permission and limit cases where they apply.
- **No implementation.** Criteria say what, never which table or framework.

A story that needs more than about five criteria, or cannot be finished inside one
cycle on the project's scale, should be split — by workflow step, by user type, by
happy path versus edge cases, or by data variation.

## Discovery items

An item still in discovery does not get build stories. Break it into **timeboxed
knowledge stories** instead: each names the question, the method (interview,
prototype, spike, data pull), the timebox, and the evidence that answers it.
Acceptance criteria for these describe the evidence produced, not software.

## Sizing and dependencies

Size relatively, against stories the team already knows, on the project's scale.
Mark anything that cannot be sized as *needs a spike* rather than guessing. List
dependencies between stories and on outside teams; flag a story that blocks more
than two others as a candidate to move earlier or split.

## Critique

Check every story against the criteria bar and the split rule, look for epics with
no user-visible first story, missing edge-case stories, and sizes that disagree
with similar stories. Report by story; rewrite only if asked, into a new file.

## With no slot filled

Defaults: hierarchy epic → story, T-shirt sizes (XS–XL), drafts at
`planning/drafts/<epic-slug>/`. Say so in the output, and offer back any sizing
scale or hierarchy names the operator used as a proposed `planning-conventions`
section. If a tracker is connected, crew's `learn` can draft the hierarchy and
sizing sections from its issue types and estimate field.
