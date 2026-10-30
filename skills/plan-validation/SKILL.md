---
name: plan-validation
description: Use when deciding whether a phase can advance, whether work is complete, or what evidence “done” requires. Defines acceptance evaluation, validation-gate promotion, invalid completion signals, and the closing retro that hands lessons to learn.
tier: concept
requires: []
---

## What a validation gate is

A validation gate is a boolean condition that must be true before the next phase begins. It is stated explicitly in the plan:

```markdown
### Validation Gate (Phase 1 → Phase 2)
- All unit tests pass (`uv run pytest`)
- No ruff errors (`uv run ruff check`)
- PR opened and review requested
```

Gates are checkable — not "looks good" but "exit code 0" or "PR state is OPEN."

## Checking acceptance criteria

For each task in the completed phase:

1. Re-read the task's acceptance criteria verbatim
2. Run or verify each criterion against the actual artifact (code, manifest, PR, vault note)
3. Record: met / not met / not checkable

If any criterion is "not met": the task is incomplete. Either re-run the task or raise a delta.

If any criterion is "not checkable": surface it as an open question before advancing. A criterion that can't be verified is a criterion that doesn't exist.

## Promotion checklist

Before advancing to the next phase:
- [ ] All tasks in current phase have acceptance criteria marked met
- [ ] Validation gate conditions are all satisfied
- [ ] No unresolved deltas from this phase
- [ ] Every decision this phase raised has a closing record (key, the human's words or the evidence that made it moot, date)
- [ ] Every loop-back this phase opened met its written exit or was escalated, and the plan has used no more than its budget of two (per `plan-execution`)
- [ ] Artifacts from this phase are in a state the next phase can consume (merged PRs, published vault notes, applied manifests)
- [ ] No protected seams were crossed without human sign-off

## What does NOT count as validation

- "The agent said it was done" — verify independently
- "The code looks correct" — run the tool that checks it
- "No errors were mentioned" — check exit codes, not absence of error messages
- "It worked before" — check the current state, not prior history
- "The decisions were listed" — a phase is not complete while a decision it raised has no closing record
- "Another round fixed it" — a loop-back counts only against the exit written before it started; a round that ends because nobody found more is not an exit

## When criteria conflict

If acceptance criteria conflict with each other or with the plan's stated goal, surface it as a delta before attempting to satisfy them. Don't resolve ambiguity silently.

## Recording gate promotion

When a validation gate passes, record it in the plan:

```markdown
### Gate: Phase 1 → Phase 2
**Promoted:** 2026-05-11
**Verified by:** Lead
**Evidence:** pytest exit 0 (run log in PR #251 CI), ruff exit 0, PR #251 opened
```

This creates an audit trail. If Phase 3 fails, you can trace back to which gate last passed and when.

## Retro: what the plan taught

When a plan's last gate passes, run a retro before closing it, and after any
reviewer pass: a review can overturn a finding the retro would otherwise keep.

1. List the signals the plan raised: corrections from the operator, steps that
   failed more than once, tool denials, reviewer findings the work had to fix,
   and Doctor rows the work left `DEGRADED`. The plan's delta history, review
   records and gate records hold most of them.
2. Hand them to `learn` as its experience source. It drafts proposals into the
   project's declared queue, or only reports them when no queue is declared, and
   never applies one. Promotion stays the operator's.
3. Record the outcome in the last gate record:

```markdown
**Retro:** 2026-05-14-lint-before-review (draft), 2026-05-14-test-target (needs-recurrence)
```

or `**Retro:** no lessons` when nothing would change the next session.

The retro never holds a gate. Work that met its criteria is done, and its
lessons wait in the queue for review. Under a supervising host whose task
contract defines knowledge capture, follow it instead, per the reporting
contract.
