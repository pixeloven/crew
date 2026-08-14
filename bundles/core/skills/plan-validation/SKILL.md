---
name: plan-validation
description: How to check whether a plan phase is complete — acceptance criteria evaluation, validation gate promotion, and what counts as done. Load when Lead is deciding whether to advance from one phase to the next.
tier: concept
requires: []
audience: [crew]
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
- [ ] Artifacts from this phase are in a state the next phase can consume (merged PRs, published vault notes, applied manifests)
- [ ] No protected seams were crossed without human sign-off

## What does NOT count as validation

- "The agent said it was done" — verify independently
- "The code looks correct" — run the tool that checks it
- "No errors were mentioned" — check exit codes, not absence of error messages
- "It worked before" — check the current state, not prior history

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
