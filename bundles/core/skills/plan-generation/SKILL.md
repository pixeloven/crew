---
name: plan-generation
description: How to propose, structure, and iterate plans in chat mode — when a plan is warranted, the high-level checklist → detailed spec progression, phase/dependency/success-criteria format, and the handoff to autonomous execution. Load when developing a plan with the operator before execution begins.
tier: concept
requires: []
audience: [crew]
---

Plans are first-class artifacts that bridge chat-mode collaboration with autonomous execution. When asked to plan work, produce a structured plan rather than jumping to implementation.

## When to Generate a Plan

Generate a plan when:
- The work spans multiple steps, agents, or repos
- The outcome requires sequenced or parallel execution
- The human needs to approve scope before work begins
- The task will be handed off to autonomous execution

Skip the plan for single-step, bounded tasks that can be executed immediately without approval.

## Plan Structure

Plans follow progressive elaboration. Start with a high-level checklist; refine into a detailed spec before autonomous execution.

### High-Level Checklist (produce this first in chat)

```markdown
# Plan: <title>

## Goal
One sentence describing the intended outcome.

## Phases
1. **Phase name** — what happens, who does it
2. **Phase name** — what happens, who does it
...

## Dependencies
- Phase 2 requires Phase 1 output
- Phases 3 and 4 can run in parallel

## Success Criteria
- [ ] Criterion one
- [ ] Criterion two

## Risks and Assumptions
- Risk: ...
- Assumption: ...

## Open Questions
- Question that needs resolution before execution
```

### Detailed Spec (add before autonomous execution)

Extend each phase with:

```markdown
## Phase N: <name>

### Tasks
- [ ] Task description
  - Agent: Implementer
  - Acceptance criteria: specific, checkable condition
  - Recovery: what to do if this task fails

### Validation Gate
What must be true before Phase N+1 begins.
```

## Format Rules

- Human-readable prose for the high-level; structured sections for the detailed spec
- Markdown with consistent section headers — both humans and Lead can parse it
- For feature implementation tasks: the plan (a plan-mode outcome persisted to the vault) is the execution contract for Implementer; `plan-execution` covers how it runs
- Express parallelism explicitly: "Phases A and B can run concurrently"
- Express convergence explicitly: "Phase C begins only when A and B are both complete"

## Iteration in Chat

- Propose the plan, then ask for feedback before locking it
- When the human pushes back, update the plan in place — don't produce a new document
- Once the human approves, the plan is ready for execution or ticket creation
- Record the approved plan in the project's plan store — a vault note, an issue attachment, or an in-repo location the project designates — so it survives the session and is available for autonomous pickup

## Handoff to Autonomous Execution

When a chat-mode plan moves to autonomous execution:
1. Ensure the detailed spec is complete (acceptance criteria, agent assignments, recovery strategies)
2. Attach the plan to the GitHub issue that will trigger autonomous dispatch
3. Lead reads the plan from the ticket and dispatches worker agents per its structure
