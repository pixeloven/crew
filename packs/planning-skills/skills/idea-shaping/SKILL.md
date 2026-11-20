---
name: idea-shaping
description: Use when someone has an idea or a problem worth writing down and wants it turned into a card the team can discuss, or a card grown into a short narrative in the project's own format. Drafts only.
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [planning-conventions]
---

# Idea shaping

Turn a raw signal into something a product team can weigh: first an **idea card**
small enough to capture in minutes, then, when the idea earns it, a narrative that
states the problem sharply and names what would test it. Where the project has a
`planning-conventions` local skill, its hierarchy names, narrative format and draft
location outrank the defaults below.

This skill writes Markdown drafts and nothing else. Putting an item in a tracker is
[`tracker-sync`](../tracker-sync/SKILL.md)'s job, and only when the operator asks.

## Depth modes

Pick the mode from what was asked and what came in; the operator can name a
different one.

| Mode | Use when | Output |
|---|---|---|
| **Quick** | something needs capturing — a quote, a hallway thought, a request | an idea card. Ask at most three questions, then draft it with every gap marked |
| **Thorough** | a card or a paragraph with a known problem and audience needs writing up | a narrative in the project's format, with the smallest version that tests the riskiest assumption |
| **Critique** | an existing card or narrative | a completeness audit: what is missing, vague, or asserted without evidence |

A marked gap is a finished answer for now; do not hold the draft back to fill it.

## The idea card

```markdown
---
kind: idea
title: <verb-led, outcome-focused — "Let returning buyers reorder in one step">
stage: <first stage, or blank>
theme:
tracker-key:
---

**Signal:** where this came from — who said or saw what, when. Quote if you can.
**Problem:** what is hard, slow, risky or missing today, for whom.
**Who:** the user or customer segment, as specifically as the signal allows.
**Why now:** what changed, or what it costs to wait.
**Hunch:** the first idea for a solution — labelled as a hunch, not a commitment.
**How we'd know:** the signal or metric that would show it worked.
**Unknowns:** the questions this card cannot answer yet.
```

Keep the problem and the hunch apart. A card whose problem statement names the
solution ("users need a reorder button") is the most common failure; rewrite the
problem until it would still be true if the hunch were wrong.

## Thorough: the narrative

Take the shape from the **Narrative format** section of `planning-conventions`,
and keep to its length limit. When that section is empty, write three parts:

1. **Problem** — what hurts, for whom, and the evidence the card has for it.
2. **Proposal** — the direction, stated as a bet, and the riskiest assumption inside
   it. Then the smallest version that would test that assumption, what it would
   cost in the project's capacity unit, and what it would leave untested. If a
   cheaper test of the same assumption exists, say so beside it; choosing is the
   team's call.
3. **Open questions** — what the team must find out, each with who could answer it.

## Critique: completeness audit

Check each card field and narrative section: present, vague, or missing. Flag
asserted evidence with no source, a problem phrased as a solution, a "who" of
"all users", and an absent success signal. Report findings; do not rewrite the
draft unless asked, and if asked, write a new file beside the original.

## Hand-off

The card or narrative is done here; say where it goes next.

- Pass it to [`theme-portfolio`](../theme-portfolio/SKILL.md) when the question is
  what it belongs with or how big a bet it is: it spans several teams or cycles,
  or it overlaps items or themes the operator has mentioned.
- Pass it to [`story-breakdown`](../story-breakdown/SKILL.md) when the direction is
  agreed and the team is ready to split it into deliverable pieces.
- Otherwise it stays a draft until someone asks for more.

## With no slot filled

Use the defaults: hierarchy idea → epic → story, the problem / proposal / open
questions shape, drafts at `planning/drafts/idea-<slug>.md` in the working
repository (ask before creating the directory). Say in the output that generic
conventions were used, and offer the operator a proposed `planning-conventions`
section for anything they corrected during the session — the hierarchy names, the
narrative shape, the draft location — so the next run does not have to ask. Crew's
`onboarding` can take that proposal from there.

## Edge cases

- **A signal passed on second-hand:** write **Signal** as who relayed it and when,
  and mark the original speaker or source as a gap. Do not upgrade "a customer
  said" into a quote nobody can trace.
- **A hunch that names no problem:** put it under **Hunch** and leave **Problem**
  marked open rather than writing one to fit. Ask who would be worse off if the
  hunch never happened; the answer, if there is one, is the problem.
- **A card that repeats an existing draft:** before writing, look through the draft
  location for cards with a similar title or problem. If one matches, show it and
  offer to merge the new signal into it instead of starting a second card.
