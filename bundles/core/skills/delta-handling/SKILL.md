---
name: delta-handling
description: How to propose, evaluate, and record plan deltas during autonomous execution. Defines the two delta classes — auto-approvable vs human-escalated — and the recording format. Load when Lead is evaluating a worker agent's proposed deviation from a plan.
tier: concept
requires: []
audience: [crew]
expects-local: [protected-seams]
---

A delta is any proposed change to a plan in progress — a task approach, scope, ordering, or acceptance criterion. Worker agents propose deltas; Lead evaluates them.

## Delta lifecycle

1. Worker agent identifies an issue during task execution
2. Agent drafts the delta: what to change, why, what the risk is
3. Lead evaluates the delta against the two classes below
4. Lead auto-approves or escalates
5. Plan is updated to reflect the delta (approved or escalated)
6. All deltas recorded in the plan history — approved or not

## Auto-approvable (Lead judges, no human needed)

| Class | Description |
|---|---|
| Transient retry | Same task, same approach, no scope change. Retrying after a rate limit, network error, or flaky tool. |
| Minor task reordering | Swapping two independent tasks with no dependency between them. The outcome is identical. |
| Approach substitution within scope | Different tool or implementation technique to achieve the same stated outcome. Scope unchanged. |
| Acceptance criteria clarification | Making an acceptance criterion more specific without raising or lowering the bar. No new requirements added. |

Lead may auto-approve without pausing execution. Record the decision.

## Always escalate to human

| Class | Description |
|---|---|
| Scope expansion | Tasks or deliverables not in the original plan. Even if beneficial, a human decides. |
| Rollback | Reverting work already completed. High risk of data loss or state divergence. |
| Seam crossing | A registry seam touched without prior flagging. See the project's protected-seams registry skill (e.g. Harmony's `harmony-protected-seams`). |
| Risk or auth change | The change alters the risk profile, or brings secrets/auth surfaces into scope. |
| Downstream impact | Changes that affect another agent's assigned task or expected input. |
| Exit/completion criteria change | The definition of "done" for the plan or a phase is being altered. |

For escalations: pause execution, surface the delta clearly (what changed, why, what the risk is), wait for human decision before resuming.

## Delta record format

Append to the plan's history section after every delta:

```
## Delta log

### Delta <N> — <date>
**Proposed by:** <agent>
**Type:** <auto-approvable class | escalation class>
**Decision:** Auto-approved by Lead / Approved by the operator / Rejected
**What changed:** one sentence describing the modification
**Why:** one sentence explaining the trigger
**Risk:** one sentence on what could go wrong
```

## Examples

**Auto-approved — transient retry:**
> Delta 1 — Worker hit GitHub API rate limit on PR creation. Retrying same task after 60s backoff. Auto-approved.

**Escalated — scope expansion:**
> Delta 2 — Worker proposes adding integration tests to the PR. Integration tests were not in the original plan. Pausing. Operator: should we expand scope or defer tests to a follow-up issue?

**Escalated — seam crossing:**
> Delta 3 — Worker modified the ExternalSecret refreshInterval to "1h" to simplify debugging. This crosses the secret management contract seam. Reverting change. Operator: please advise.
