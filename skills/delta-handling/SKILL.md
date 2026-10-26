---
name: delta-handling
description: Use when a worker proposes deviating from an active plan, when deciding whether a change needs sign-off, or when recording a mid-execution change. Defines auto-approvable vs human-escalated deltas.
tier: concept
requires: []
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
| Seam crossing | A registry seam touched without prior flagging. See the project's protected-seams registry skill. |
| Risk or auth change | The change alters the risk profile, or brings secrets/auth surfaces into scope. |
| Downstream impact | Changes that affect another agent's assigned task or expected input. |
| Exit/completion criteria change | The definition of "done" for the plan or a phase is being altered. |
| Repeated same-theme findings | Successive review rounds keep finding defects in the fixes around one questionable abstraction, and each fix accretes more machinery around it. Escalate before another fix round. |

## A review finding cannot amend the accepted ask

The accepted ask is the requirement the plan was built from. A review finding can show the work falls short of it; it cannot add to it. A fix that adds a guarantee, subsystem, compatibility surface or monitoring requirement the ask did not contain is scope expansion, whatever the finding's label ("security", "required"). Escalate it as scope expansion instead of starting a fix round for it. A finding that the work fails the ask itself is still fixed in the round.

## Escalating a scope expansion or repeated findings

An escalation under either of the two rules above states:

1. **Original requirement** — what the accepted ask says, quoted where possible.
2. **Proposed expansion** — what the finding or the next fix round would add.
3. **Smallest compliant alternative** — the least change that satisfies the ask as written.
4. **Consequences of each** — what taking the expansion costs, and what declining it risks.
5. **Recommendation** — which to take, and why.

For escalations: pause execution, surface the delta clearly (what changed, why, what the risk is) as a decision with a `[key=<slug>]`, per the reporting contract, and wait for the human's decision before resuming. The escalation closes only when its record carries that key, the human's words or the evidence that made it moot, and the date.

Under a supervising host, route an escalation through the decision channel its task contract names, and use its record format when it defines one, per the reporting contract's *A supervising host's contract wins* rule. When the run is unattended, record the delta and the decision it needs there and stop instead of waiting; continue only on a safe default the host contract allows.

## Delta record format

Append to the plan's history section after every delta:

```
## Delta log

### Delta <N> — <date>
**Proposed by:** <agent>
**Type:** <auto-approvable class | escalation class>
**Decision:** Auto-approved by Lead / Approved by the operator / Rejected
**Decision record:** (escalations only) `[key=<slug>] closed <YYYY-MM-DD>: "<the operator's words>"`, or `moot <YYYY-MM-DD>: <evidence>`
**What changed:** one sentence describing the modification
**Why:** one sentence explaining the trigger
**Risk:** one sentence on what could go wrong
```

## Examples

**Auto-approved — transient retry:**
> Delta 1 — Worker hit GitHub API rate limit on PR creation. Retrying same task after 60s backoff. Auto-approved.

**Escalated — scope expansion:**
> Delta 2 — Worker proposes adding integration tests to the PR. Integration tests were not in the original plan. Pausing. `[key=delta-2-integration-tests]` Operator: should we expand scope or defer tests to a follow-up issue?
>
> Closing record: `[key=delta-2-integration-tests] closed 2026-05-12: "Defer them, open a follow-up issue."`

**Escalated — review finding outside the ask:**
> Delta 3 — Reviewer marks "add retry telemetry and an alert" as required (security). The ask was to fix the token refresh race. Original requirement: refresh tokens without the race. Proposed expansion: a new metric and alert. Smallest compliant alternative: the race fix with a regression test. Consequences: the expansion adds a monitoring surface someone must own; declining leaves retries visible only in logs. Recommend the race fix now and a follow-up issue for telemetry. `[key=delta-3-retry-telemetry]` Operator: expand scope or defer?

**Escalated — repeated same-theme findings:**
> Delta 4 — Round 3 findings are again defects in the cache-invalidation wrapper added in round 1 to answer a round-1 finding. Each fix has added more machinery around the wrapper. Pausing before round 4 with the five elements above. `[key=delta-4-cache-wrapper]` Recommend dropping the wrapper for the plain invalidation call the ask needed.

**Escalated — seam crossing:**
> Delta 5 — Worker modified the ExternalSecret refreshInterval to "1h" to simplify debugging. This crosses the secret management contract seam. Reverting change. `[key=delta-5-refresh-interval]` Operator: please advise.
