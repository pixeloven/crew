---
name: plan-execution
description: How Lead reads an approved plan, dispatches worker agents per its phase structure, monitors acceptance criteria and validation gates, handles deltas, and drives execution to completion. Load when executing a persisted plan in autonomous mode.
tier: concept
requires: []
audience: [crew]
expects-local: [protected-seams]
---

Plan execution is Lead's primary autonomous-mode responsibility. When a plan arrives via ticket or is approved in chat, Lead owns it end-to-end.

## Reading a Plan

Before dispatching any agent:
1. Read the full plan — both the high-level checklist and the detailed spec
2. Identify the phase sequence and any parallel phases
3. Confirm all acceptance criteria are present and checkable
4. Flag any open questions that must be resolved before starting — don't proceed with ambiguous scope

## Dispatching Worker Agents

Dispatch agents per the plan's phase structure:

- **Sequential phases**: dispatch the next agent only after the previous phase's validation gate passes
- **Parallel phases**: dispatch multiple agents simultaneously; wait for all to complete before the convergence point
- **Agent selection**: match the task to the right agent role (Implementer for write work, Reviewer for review, Investigator for diagnosis, Researcher for option analysis)

For feature implementation tasks, Implementer works from the spec's plan.md:
phases execute in order, each gated by its verification criteria.

## Checking a phase (not monitoring it)

You do not see a worker's intermediate output — only its final result (see `orchestration-patterns`). Evaluate **after** each dispatch returns, from the returned artifact:

- Check that acceptance criteria are met — they must be checkable from the artifact alone, not from having watched the work
- Check that no protected seams were crossed without flagging (per the project's protected-seams registry skill, if it defines one)
- Check that the validation gate condition is satisfied before advancing

If the result is wrong or incomplete, prefer **steering that worker** (resume / follow-up, per the harness table in `orchestration-patterns`) over dispatching a fresh one — the resumed worker keeps its context.

## Delta Handling

When a worker agent proposes a delta (a change to the current plan), classify and route it per `delta-handling` — that skill owns the auto-approve vs escalate classes, the escalation procedure, and the record format. Record all deltas — approved or escalated — in the plan's history.

## Convention Enforcement

During execution, challenge any agent output that:
- Violates the project's platform conventions (per its conventions local skill)
- Crosses a protected seam without flagging it
- Deviates from the plan's stated scope without raising a delta

Challenge means: surface the violation, explain why it's a problem, ask the agent to correct before proceeding. Do not silently accept non-compliant output.

## Completion

A plan is complete when:
- All acceptance criteria across all phases are met
- All validation gates have passed
- No unresolved deltas remain
- A completion summary is posted to the originating ticket or chat session

The completion summary should include: what was done, any deltas that occurred and how they were resolved, and any follow-up issues opened.
