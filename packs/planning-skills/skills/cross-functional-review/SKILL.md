---
name: cross-functional-review
description: Use when asking which cross-functional partners (security, privacy, legal, data and others) a product concept needs, how early, and why. Logs each finding by its impact on the plan, applies the project's review lenses, and drafts new lenses.
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [review-lenses]
---

# Cross-functional review

Tell a product team, before design settles, which partner functions must weigh in,
how early, and what they will need. The unit of work is the **finding** — one thing
in the concept a partner would have a view on — not the partner. Partners follow
from the findings. The point is to surface the few findings whose answers could
change *what* gets built while changing it is still cheap, and to keep everything
else out of the way. Where the project has a `review-lenses` local skill, its
lenses outrank the defaults below.

## Impact levels

Every finding gets one of three levels:

| Level | Means |
|---|---|
| **Reshapes** | their answer could change the solution, scope, markets or timeline |
| **Adds work** | the shape holds, but there are tasks or artifacts the team must plan and size |
| **Covered** | existing practice or a checklist the team already follows handles it; log it and move on |

The level says how much is at stake; it does not set the date. Timing comes from
the finding itself: name the decision it bears on — the choice of solution it could
overturn, the market it could rule out, the estimate it adds to — and the partner
must weigh in before that decision is made. Two Reshapes findings can fall due at
very different points in the same plan.

A lens whose findings are all **Covered** is worth one line, not a meeting.

"No partners needed, because …" is a valid result. Say it with the reason.

## Lenses: defaults and the slot

A lens is a way of reading the concept on one partner's behalf. The pack ships five
defaults; the slot refines them by name:

- a slot section with a default's name **overrides** that default entirely;
- a section with a new name **adds** an org-specific lens;
- a section whose body is `n/a` **switches that lens off**, with its reason;
- a default with no slot section runs as shipped.

Every output lists each lens with its source: *slot*, *default*, or *off (slot)*.

| Default lens | Reads for | A Reshapes finding looks like, e.g. |
|---|---|---|
| `security` | a login, permission, external integration, file upload, payment path, or new attack surface | a new trust boundary; letting one user act for another |
| `privacy-legal` | personal data collected, shared or inferred; a new market; changed terms, consent or claims | a new purpose for existing data; minors; cross-border transfer |
| `data` | events, metrics, models or reports created or changed; success that needs measuring | a new source of truth; a metric definition others depend on |
| `accessibility` | any changed user-facing surface or interaction pattern | a new interaction model; time-limited or gesture-only flows |
| `operations-support` | what customers can now do, break or ask about; new load or a new failure mode | a new manual process; a change support cannot see or reverse |

For defaults, the partner is named by function, never a person. A slot lens has
two parts: the **questions this partner asks** of a concept, and the **route** —
which role answers and how to reach them.

## Depth modes

| Mode | Use when | How it runs | Output |
|---|---|---|---|
| **Quick** | an early concept, a "who do we need?" | one agent reads the concept through every active lens in turn | the **Who to loop in** roll-up, with each Reshapes finding written out and the rest counted |
| **Thorough** | a concept heading into design | one subagent per lens with anything to say, in parallel | the full **review ledger** and its roll-up |
| **Critique** | a ledger already exists, or someone holds that no partner is needed | one agent, reading as a sceptic | what the earlier pass got wrong: findings levelled too low, findings the concept has grown since, and Reshapes findings the plan has not yet absorbed into its scope or timeline |

Choose from the input's maturity and what was asked; the operator can override.
Critique does not ask whether partners signed off — that is a gate question for
[`readiness-gates`](../readiness-gates/SKILL.md). It asks whether the ledger still
tells the truth about the concept as it stands.

## Steps

1. **Get the concept.** An idea card, a requirements doc, or a paragraph. Ask for
   the surfaces touched and the data involved if neither is clear. In Critique, also
   get the earlier ledger, or the claim that none was needed.
2. **Resolve the lens set**: defaults merged with the slot, as above.
3. **Read through each lens** and write down every finding it produces, however
   small. A lens with no findings is recorded as *quiet*, with the reason.
4. **Level each finding** — inline in Quick and Critique, by dispatch in Thorough.
   When unsure between two levels, take the higher and say what would lower it.
5. **Build the ledger**, then derive the roll-up from it. Never write the roll-up
   first; a partner with no finding behind them is not on it.

## Thorough: dispatch per lens

Dispatch crew's `reviewer` role once per lens with anything to say, by the name the
harness registers it under — crew's roles are namespaced (e.g. `crew.reviewer` on
pi; the plugin-namespaced reviewer on Claude Code and Codex), and a bare `reviewer`
may reach a different agent. Give each dispatch: the concept text, that one lens's
full definition (slot or default), and the ask — *list each finding this lens has in
the concept, give each an impact level (reshapes / adds work / covered), name the
decision each one bears on, and say what the partner needs from the team; "nothing
that reshapes the plan" is an acceptable answer with a reason.* If the harness cannot
dispatch subagents, run the lenses one at a time inline and say so.

## The review ledger

One row per finding, in three groups — **Reshapes**, then **Adds work**, then
**Covered** (Covered rows may collapse to a single line per lens):

| Finding | Impact | Who must weigh in | By when | What they need from us | Lens (source) |
|---|---|---|---|---|---|

- **Finding** is phrased as a fact about the concept ("stores a dietary note about
  someone other than the account holder"), not as a partner's name or a worry.
- **By when** names the decision the finding bears on and lands before it ("before
  the gift flow is designed", "before the epic is sized"), not a date read off the
  level.
- **What they need from us** is a concrete hand-over: a data inventory, a threat
  sketch, a claims list. "A meeting" is not one.

Under the ledger, list the **open questions** only a partner can answer, each tied
to the finding it comes from.

## Who to loop in

Read this off the ledger; never write it on its own, so no partner appears without
a finding behind them. Give one short entry per partner, soonest first:

- **<Partner>** — needed <earliest by-when>, for: <finding>; <finding>.

A partner whose findings are all Covered gets no entry; name them in one line
beneath ("covered by existing practice: …"). Finish with the lens list — every
lens, its source, and *fired* or *quiet*.

## Authoring a lens

A lens works best in the partner's own words, so draft it from material they
already wrote rather than from a blank form. Ask the operator for the partner's
intake checklist, or a few of their past review comments, and turn what keeps
coming up into the **Questions this partner asks**. Add the **Route** — the role
that answers and how to reach it. Then hand the draft to the partner, through the
operator, to edit: they know which questions matter and which never do.

Deliver it as a section in the `review-lenses` stub format for the operator to
promote. Never write it into their overlay yourself. With no material to start
from, draft three or four questions from the default lens nearest to it and say
that the partner has not seen them yet.

## With no slot filled

All five defaults run, and the output says so. Recommend authoring a lens for any
partner function the operator mentioned that the defaults do not cover, and an `n/a`
for any default they said does not apply to them.
