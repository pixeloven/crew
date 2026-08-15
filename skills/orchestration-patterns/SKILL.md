---
name: orchestration-patterns
description: Composing work across multiple agents — sequential, parallel and mixed shapes, the dispatch packet a worker needs, convergence, writer isolation, and how to bind each of those to your harness's actual primitives rather than describing them in prose. Load when planning work that spans several agents, dispatching a worker, or deciding how to split and reconverge a task.
tier: concept
requires: []
---

## The model: hub-and-spoke, bound to your harness

One agent (Lead) dispatches typed workers, each with isolated context, and mediates convergence itself. Workers return results; they do not talk to each other.

That is a **policy choice with evidence behind it**, not a limitation to work around. Every harness this foundation supports converges on parent-spawns-typed-children with isolated context and structured results. Peer-to-peer between agents is either absent or scoped to one runtime, and cross-instance agent-to-agent messaging exists nowhere. Designs that assume a swarm will not port.

Two layers, and keeping them apart is what makes this durable:

- **Judgment stays here, and is harness-agnostic** — how to decompose a plan, what a dispatch must carry, when to converge, which deviations escalate, what "done" means. No harness supplies any of it.
- **Mechanism belongs to the harness** — how a worker is spawned, isolated, steered, and awaited. Bind to what your harness actually provides rather than describing dispatch in prose.

When the two conflict, the harness wins on mechanism and this skill wins on judgment.

## Binding mechanism to your harness

Look these up before relying on them; harness capabilities move faster than documentation about them (see the verification-date rule in `agent-platform-design`).

| Need | Claude Code | pi.dev | Codex |
|---|---|---|---|
| Dispatch a worker | subagent dispatch; `workflows/` for scripted fan-out | `workflowScript` — `runs.run(key, {agent, task})` | `spawn_agent(role)` from `.codex/agents/*.toml` |
| Fan out and await | `pipeline()` / parallel dispatch | `runs.all([...])` — every child settles, ordered outcomes | parallel `spawn_agent` + `wait_agent` |
| Isolate a writer | `isolation: worktree` (**base defaults to the repo default branch, not parent HEAD**) | `worktree: true` | per-role `sandbox_mode` |
| Correct mid-run | `SendMessage` (auto-resumes, full history retained) | `steer` / `follow_up` | `followup_task` |
| Stop | `TaskStop` (by spawned name) | — | `interrupt_agent` |
| Gate on a check | acceptance criteria in the dispatch | `gate: "<command>"` | acceptance criteria in the dispatch |
| Carry state across dispatches | the plan store | mission `state.get/set` | the plan store |

**Where a harness gives you a primitive, use it** — a scripted fan-out that awaits its children is more reliable than prose instructing an agent to remember to wait. **Where it doesn't, the judgment sections below still apply.**

Two asymmetries worth designing around: only some harnesses can *stop* a worker, and only some carry durable state between dispatches. If a plan depends on either, check first and fall back to bounding the work instead.

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

Use isolation for genuinely parallel independent work; for ordinary single-agent in-repo implementation, write to the current tree.

## The dispatch packet

A worker starts cold. It does not inherit your conversation, your reasoning, or your assumptions — only what you hand it. Every dispatch carries:

1. **The task** — one scoped unit, small enough that a wrong result is cheap to discard.
2. **Acceptance criteria** — checkable **from the returned artifact alone**. If verifying requires having watched the work, the criteria are wrong.
3. **Context that isn't obvious from the artifacts** — the constraint you know and the worker can't infer.
4. **Where to work** — repo, branch, worktree.
5. **A plan reference** it can pull for the wider picture.

Expect back: the artifact, a status (`completed` / `blocked` / `needs-decision`), and any proposed deltas.

**When a result is wrong, prefer steering that worker over dispatching a fresh one** where the harness supports it — the resumed worker keeps its context; a new one starts cold and repeats the discovery.

## Inter-agent handoff

When handing off between agents (sequential), include in the handoff:
1. What was produced (artifacts, PR links, vault notes)
2. What the next agent needs to know (context that isn't obvious from the artifacts)
3. What the acceptance criteria are for the next phase

Don't assume the next agent will read the full conversation history. Be explicit.

## Steer or inspect a worker — you get its final result, not its intermediate output

A dispatching agent receives the worker's **final result**; intermediate tool calls and output stay inside the worker. Design around that: bound the work rather than watching it, and use the steering primitives below when a result needs correcting.

| Need | Claude Code | pi.dev | Codex |
|---|---|---|---|
| Correct a worker mid-run | `SendMessage` (auto-resumes a completed agent, full history retained) | `steer` / `follow_up` | `followup_task` |
| Stop a worker | `TaskStop` (by the name the agent was spawned with) | — | `interrupt_agent` |
| Inspect what's running | sibling roster (**snapshot at spawn time** — later agents are invisible) | `subagent_wait` `details.completions` | `list_agents`, `/agent` |

Verify these against your harness's current docs before relying on an absence — this table is a point-in-time snapshot and the harnesses move.

Design implication: bound the work instead of watching it. Give each dispatch a scope small enough that a wrong result is cheap, acceptance criteria checkable from the returned artifact alone, and — where the harness supports it — a turn or budget cap. When a returned result is wrong or incomplete, prefer resuming/steering that worker over re-dispatching a fresh one: the resumed agent retains its context, a new one starts cold.

Runtime-level failure signalling (exit codes, result-file contracts, retry policy) belongs to the consumer's agent-runtime local skill, not here — it is a property of a specific autonomous runtime, not of dispatch.
