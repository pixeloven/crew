---
name: requirements-review
description: Use when reviewing, scoring or refining a PRD or requirements doc. Asks whether each reader — approver, builder, tester, operator, analyst — can act on it, coaches the gaps, or runs a gap-filling Q&A into a new draft.
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [prd-bar, planning-stages]
---

# Requirements review

A requirements doc exists so that other people can act without asking the author.
Review it by standing in for each of those people in turn and asking whether they
could do their job from the page alone. Where the project has a `prd-bar` local
skill, its checks, sections, failure modes and labels outrank the defaults below;
where it has a `planning-stages` local skill, only the checks due at the item's
stage count.

## Depth modes

| Mode | Input looks like | Output |
|---|---|---|
| **Quick** | no doc yet, or an idea card | the questions each reader will ask, in the order to answer them, and the sections to start from |
| **Thorough** | a draft with gaps | a refine Q&A that fills them, written into a **new** draft file |
| **Critique** | a doc presented for sign-off | a reader-by-reader verdict with quoted evidence, failure modes found, and coaching |

Choose from the input; the operator can override. Ask which stage the item is in if
it is not obvious: a doc for an item in discovery owes its readers the question and
the evidence so far, not scope detail it should not have yet.

## The readers (used while `prd-bar` is empty)

Each reader has a few yes/no checks. A check is answered **yes** only when you can
quote the passage that answers it; otherwise **no**, or **not due** when the stage
does not ask for it yet.

| Reader | Needs to | Checks |
|---|---|---|
| **Approver** | say yes or no | Is the ask stated in the first screen? · Is the problem tied to a named group of people, without naming the fix? · Is there evidence, with each unproven claim marked as a bet? · Does it say what happens if we do nothing, or what else was weighed? |
| **Builder** | start work without guessing | Is what is in and what is out written down? · Is the solution a direction they can challenge, not a finished design? · Are the things it waits on (teams, systems, vendors) named? |
| **Tester** | tell whether it works | Are the expected behaviours written so two people would check them the same way? · Are the awkward cases (empty, failed, partial, reversed) covered or deferred on purpose? |
| **Operator** | run it after launch | Does it say who downstream is affected (support, operations, partners) and how they learn of it? · Does it say how to roll out and how to back out? · Does each named risk have an owning role? |
| **Analyst** | judge the result | Is there one number that will say whether it worked, with today's value and the target? · Does it say what result would make us stop or change course, and when that call is made? |

Anything still unanswered belongs in an **Open questions** list with who answers it
and by when; an honest open question beats a confident gap.

## Verdicts

Give each reader one label:

- **Ready** — every due check is yes.
- **Needs work** — some due checks are yes, at least one is no.
- **Missing** — no due check is yes; this reader would send the doc straight back.

The doc's verdict is a sentence, not a grade: *who can act on it today, and who
cannot yet*. A doc is ready for sign-off only when every reader is Ready; never
average a Missing reader away against a strong one.

## Failure modes to name

Each describes what goes wrong for a reader, so name it with the reader it fails and
the passage that shows it:

- **Buried ask** (approver) — what the approver is asked to agree to cannot be
  found without reading the whole doc.
- **Foregone conclusion** (approver) — the doc argues for one answer and shows
  nothing that was weighed against it.
- **Two readings** (builder, tester) — a key behaviour could reasonably be built or
  checked in two different ways.
- **Launch-day surprise** (operator) — a team that must act after launch is not
  mentioned, or learns of it at release.
- **Unfalsifiable** (analyst) — no result the doc describes would count as failure.

Add the local failure modes the slot lists.

## Thorough: refine Q&A

1. Run the checks silently; do not show verdicts yet.
2. Start with the reader furthest from Ready — usually the approver, since nothing
   else matters if nobody can say yes or no to it. Ask one or two questions at a time,
   and offer a candidate answer drawn from the doc when you can, so the owner
   corrects rather than composes.
3. Stop when every due reader would be Ready, or the owner says enough. Whatever
   is still unanswered goes to **Open questions**.
4. Write the result to a **new file** beside the original (e.g. `<name>.v2.md`)
   and never overwrite the source. List what changed at the top of the new file.

## Coaching

After a Critique, give at most three coaching points, each naming the reader it
unblocks and phrased as the next edit to make. Name, in one line, what already works
for its reader; it tells the author what to keep.

## With no slot filled

Use the reader checks above and the generic stages from
[`readiness-gates`](../readiness-gates/SKILL.md), and label the result *generic
checks*. If the operator's org has a template, ask for it: its headings are the best
first draft of the `prd-bar` **Required sections**, and a connected docs tool
(`mcp:docs`) lets crew's `learn` propose them. Offer the checks the operator pushed
back on during review as a proposed `prd-bar` section to promote.
