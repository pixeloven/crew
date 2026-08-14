---
name: seam-alert-routing
description: How to route seam crossing alerts — who gets notified, through what channel, and what happens next. Load when a seam crossing is detected and needs to be surfaced.
tier: concept
requires: [external:github]
audience: [crew]
expects-local: [protected-seams]
---

## Who owns seam decisions

**The project approver** (named in the project's protected-seams registry, e.g. Harmony's `harmony-protected-seams`) — primary owner. Holds final decision on all seam crossings.
**Lead** — co-enforcement. Flags seam crossings in diffs and during agent execution. Does not unilaterally approve crossings.

Neither Reviewer nor Implementer has authority to approve a seam crossing. They detect and flag; humans decide.

## Response policy: flag, don't block

The response posture is **lighter touch**. A detected seam crossing:
- Is flagged immediately and clearly
- Does not automatically block execution or PR merge
- Routes to human review for a decision

This keeps the platform moving while ensuring crossings don't go unnoticed.

## Routing by detection context

### Detected in a PR diff (Reviewer)

1. Post a PR comment with the seam finding (see `seam-detection` for format)
2. Mark the finding as **Required**
3. Tag `@<project-approver>` in the comment
4. Do not approve the PR until the project approver provides sign-off

### Detected during autonomous execution (Lead)

1. Log the crossing in the plan's delta record
2. Surface it to the project approver via a GitHub issue comment on the triggering issue
3. Pause the affected phase — do not advance until the approver responds
4. Other independent phases may continue

### Detected in a scheduled sweep (Investigator)

1. File a GitHub issue with `domain:ops` label
2. Title: `[seam] <seam-name>: <description of crossing>`
3. Body: what was detected, where, what the risk is
4. Do not auto-remediate — seam crossings are human decisions

## Escalation format

```
**Seam crossing — requires human review**

Seam: <seam name from the project's registry>
Detected by: <Reviewer / Lead / Investigator>
Location: <PR #N / issue #N / file path>
What crossed: <one sentence>
Risk: <one sentence on potential impact>

@<project-approver> — please advise before proceeding.
```

## After human decision

- **Approved:** record the approval in the plan delta log or PR thread; execution continues
- **Rejected:** revert the crossing; raise a delta if the original task can't be completed without it
- **Deferred:** note the deferral; create a follow-up issue for the seam discussion

All decisions are recorded. Don't let seam crossings resolve silently.
