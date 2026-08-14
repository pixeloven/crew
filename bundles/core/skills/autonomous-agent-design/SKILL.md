---
name: autonomous-agent-design
description: Patterns for designing autonomous agent workflows — task decomposition, tool scoping, result contracts, failure modes, and the shadow→draft→autonomous maturity sequence. Load when designing new agent capabilities or evaluating agent workflow options.
tier: concept
requires: []
audience: [crew]
expects-local: [agent-runtime]
---

## Core design principles

**Behavioral specialization → skills. Operational specialization → agents.** Most specialization pressure resolves into a skill file, not a new agent. Only add an agent when the role genuinely requires a different stance or different tool scope.

**Generic role agents, domain knowledge in skills.** Eight role agents (Lead, Triage, Investigator, Researcher, Implementer, Reviewer, Librarian, Responder) cover the work modes. Specificity flows through skill composition.

**Privilege gradient.** Read-only and draft-only agents cover most work. Implementer is the deliberate write path. Design new capabilities at the lowest privilege level that accomplishes the task.

## Task decomposition

Well-designed autonomous tasks are:
- **Bounded** — a clear start state, end state, and definition of done
- **Single-purpose** — one agent, one responsibility per task
- **Checkable** — acceptance criteria that are machine-verifiable, not "looks right"
- **Recoverable** — a defined action if the task fails (retry, escalate, or skip)

Complex work that spans multiple tasks belongs in a plan, not a single agent invocation.

## Tool scoping

Give each agent the minimum tools needed for its role:

| Agent | Write tools? | Cluster access? |
|---|---|---|
| Triage | Labels and comments only | No |
| Researcher | Vault write only | No |
| Investigator | Issues and comments | Read-only |
| Reviewer | PR comments only | No |
| Implementer | Code, manifests, PRs | No (via ArgoCD) |
| Lead | Issues, plans, dispatch | No |

Don't give an agent write access it doesn't need. A Researcher that can push code is a liability.

## Result contracts

Every autonomous agent produces a structured result. The result must be:
- Written to a structured result file at a path the runtime defines (e.g. `/tmp/agent-result.json` in Harmony's runtime)
- Parseable by the orchestrator (Lead or the runtime's exit handler)
- Sufficient for the next phase to proceed without re-reading the agent's full output

Minimum result fields: `summary`, `status` (success/partial/failed), list of artifacts produced.

## Failure modes

Design for three failure classes:

| Class | Handling |
|---|---|
| Transient | Retry with backoff — network, rate limit, temporary unavailability |
| Structural | No retry — escalate to human; task is broken |
| Success | Proceed to next phase |

The concrete signaling (exit codes, result-file status fields) is the runtime's contract — see the project's agent-runtime local skill. Harmony's runtime, for example, maps these classes to exit codes 75 / 1 / 0.

A task that silently succeeds while producing wrong output is worse than a clean failure. Validate output before signaling success.

## Maturity sequence

**Shadow → Draft → Autonomous.** Never skip stages.

| Stage | Agent behavior | Human role |
|---|---|---|
| Shadow | Runs, produces output, takes no action | Reviews output manually |
| Draft | Produces artifacts (PRs, issue drafts, comments) but does not publish | Reviews and approves before publish |
| Autonomous | Runs and publishes without review | Reviews asynchronously; intervenes on escalation |

Earn autonomy on narrow, well-understood surfaces before expanding. A reviewer that auto-merges PRs is not a reviewer — it's a rubber stamp.

## Idempotency

Autonomous agents run repeatedly — scheduled sweeps, retries, re-triggers. Every agent action must be safe to run twice:
- Opening an issue: check for duplicates before filing
- Writing a vault note: check the substrate first (see `memory-substrate` Read Routing) so you don't duplicate prior analysis
- Applying labels: idempotent by nature
- Writing code: operate on a fresh branch per task
