---
name: orchestration-patterns
description: Parallel and sequential workflow composition, convergence handling, and multi-agent coordination for Lead. Load when Lead is designing or executing a multi-agent plan.
tier: concept
requires: []
audience: [crew]
---

## Workflow shapes

### Sequential

Each phase depends on the previous phase's output. No parallelism.

```
Triage → Researcher → Lead (plan) → Implementer → Reviewer → Ship
```

Use sequential when:
- Later phases need results from earlier phases
- Resource contention makes parallelism impractical
- The risk of divergent outputs is high

### Parallel

Multiple agents work independently. Convergence waits for all to complete.

```
          ┌─→ Implementer (component A) ─┐
Lead ─────┤                              ├─→ Reviewer → Ship
          └─→ Implementer (component B) ─┘
```

Use parallel when:
- Work items are genuinely independent (no shared state, no ordering dependency)
- The plan explicitly expresses parallelism
- Sandboxing is confirmed (git worktrees, separate namespaces)

### Mixed

Sequential phases with parallel implementation inside, then sequential reconvergence:

```
Phase 1 (sequential) → Phase 2 (parallel Implementers) → Phase 3 (sequential Reviewer)
```

Most non-trivial plans are mixed.

## Expressing parallelism in plans

Plans must express parallelism and convergence explicitly:

```markdown
## Phase 2: Implementation (parallel)
Phases 2A and 2B can run concurrently.

### Phase 2A — Python changes
- Agent: Implementer
- Acceptance criteria: `uv run pytest` passes

### Phase 2B — K8s manifest changes
- Agent: Implementer
- Acceptance criteria: `kubectl kustomize build` passes

## Phase 3: Review (begins only when 2A and 2B are both complete)
- Agent: Reviewer
```

Never imply parallelism — state it. Never imply convergence — state the condition.

## Convergence handling

Before advancing from a parallel phase:
- Collect outputs from all parallel agents
- Verify each agent's acceptance criteria are met
- Check for conflicts (same file modified by two agents)
- If conflicts exist: resolve before advancing — this is a delta requiring human review

## Sandboxing parallel Implementers

Multiple Implementers writing code simultaneously need isolation. Use the harness's isolation primitive rather than assuming branches:

- **Claude Code** — `isolation: worktree` on the agent. **Landmine:** its base defaults to the repo's *default branch*, not the parent's HEAD (`worktree.baseRef: "fresh"`). Dispatching mid-plan therefore branches off `main` and silently loses the plan's in-progress work unless you set `baseRef: "head"`.
- **pi.dev** — `worktree: true` on the run.
- **Codex** — per-role `sandbox_mode` in `.codex/agents/*.toml`.

Then, whatever the primitive:
- No shared mutable state in the workspace
- PRs are independent — they can be reviewed and merged separately
- Lead coordinates merge ordering if there are dependencies

Isolation is only warranted for genuinely parallel independent work; for ordinary in-repo implementation the agent should write to the current tree.

## Inter-agent handoff

When handing off between agents (sequential), include in the handoff:
1. What was produced (artifacts, PR links, vault notes)
2. What the next agent needs to know (context that isn't obvious from the artifacts)
3. What the acceptance criteria are for the next phase

Don't assume the next agent will read the full conversation history. Be explicit.

## You cannot watch a worker mid-flight — steer or inspect instead

**A dispatching agent does not observe a worker's intermediate tool calls or output.** It gets the final result. Any pattern premised on noticing a worker "going quiet" or "stalling" mid-run is unimplementable on every harness we support — don't write plans that depend on it.

What you *can* do, per harness:

| Need | Claude Code | pi.dev | Codex |
|---|---|---|---|
| Correct a worker mid-run | `SendMessage` (auto-resumes a completed agent, full history retained) | `steer` / `follow_up` | `followup_task` |
| Stop a worker | — | — | `interrupt_agent` |
| Inspect what's running | sibling roster (**snapshot at spawn time** — later agents are invisible) | `subagent_wait` `details.completions` | `list_agents`, `/agent` |

Design implication: bound the work instead of watching it. Give each dispatch a scope small enough that a wrong result is cheap, acceptance criteria checkable from the returned artifact alone, and — where the harness supports it — a turn or budget cap. When a returned result is wrong or incomplete, prefer resuming/steering that worker over re-dispatching a fresh one: the resumed agent retains its context, a new one starts cold.

Runtime-level failure signalling (exit codes, result-file contracts, retry policy) belongs to the consumer's agent-runtime local skill, not here — it is a property of a specific autonomous runtime, not of dispatch.
