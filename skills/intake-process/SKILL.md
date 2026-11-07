---
name: intake-process
description: Use when triaging issues or PRs, labeling an unsorted backlog, choosing a handler, or defining intake conventions. Classifies domain, work type, complexity, and routing decision.
tier: concept
requires: [external:github]
---

## Domain labels

The label set itself belongs to the project — it's defined in the repo's labels. The taxonomy below is the recommended default; substitute the project's own set if it differs.

Apply exactly one `domain:*` label per item:

| Label | Applies to |
|---|---|
| `domain:infra` | Infrastructure as code, deployment manifests, and cluster or host operations (the project's stacks, for example Kubernetes, Terraform or Ansible) |
| `domain:platform` | The project's CLI, MCP servers, core libraries, agent tooling |
| `domain:ops` | Runtime health degradations, incidents, monitoring findings |
| `domain:agents` | Agent topology, skills, orchestration |
| `domain:research` | Pre-implementation option analysis, technology evaluation |
| `domain:docs` | Documentation, runbooks, specs |
| `domain:qa` | Post-deploy verification failures, regression findings |

## Work type classification

After applying a domain label, classify the work type to determine routing. This is the single routing table: Triage's role body points here rather than keeping a copy.

| Work type | Signal | Route to |
|---|---|---|
| Simple question | Single-step, answerable from what the project has written down (repo, docs, git history, corpus) | Researcher (answer from the record) |
| Failure or degradation | A failing test or CI run, a bug or symptom-only report, a workload failing, a deploy reported degraded, a host down, an alert filed as an issue | Investigator |
| Pre-implementation research | "evaluate options for...", "research...", or `domain:research` label | Researcher (option analysis) |
| Bounded write work | `domain:platform` or `domain:infra`, trivial or clear explicit scope, no design needed | Implementer |
| PR opened, no orchestrated plan | Code review needed | Reviewer |
| Multi-step / ambiguous / plan needed | More than one agent needed, unclear scope | Lead |
| Single-agent, well-scoped (non-write) | Obvious owner, bounded non-implementation task | Lead to assign |
| Touches protected seams | Any item crossing a seam in the project's registry | Flag for the operator — do not route autonomously |

Alerts reach intake only when they arrive filed as issues. A raw alert or webhook is not intake work: wire it straight to Investigator.

## Processing an issue

1. Read the title and body
2. Apply `domain:*` label
3. Classify work type
4. Post a routing comment:
   ```
   Classified as domain:<x>. Routing to <Agent> — <one-sentence reason>.
   ```
5. If routing to an agent that has a queue mechanism, add the routing label (e.g., `agent:research`, `agent:review`)

## Processing a PR

1. Check if the PR is part of an orchestrated plan (Lead-driven work has context in the PR description)
2. If yes: Lead is already tracking it; add the domain label only
3. If no: route to Reviewer with domain label applied

## Ambiguity handling

When the domain or work type is unclear:
- Default route: Lead
- Don't guess at implementation intent or priority
- Don't apply multiple `domain:*` labels — pick the primary one
- A brief "unclear scope, routing to Lead for triage" comment is correct

## What Triage does not do

- Does not make implementation decisions
- Does not access the cluster
- Does not write code or manifests
- Does not draft replies (Researcher drafts them)
- Does not re-classify items that already have a `domain:*` label from a previous pass
