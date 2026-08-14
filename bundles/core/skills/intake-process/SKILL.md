---
name: intake-process
description: How Triage classifies incoming GitHub issues and PRs — domain labels, work type, and routing decisions. Load when processing new issues, PRs, or unlabelled work items.
tier: concept
requires: [external:github]
audience: [crew]
---

## Domain labels

The label set itself belongs to the project — it's defined in the repo's labels. The taxonomy below is the recommended default; substitute the project's own set if it differs.

Apply exactly one `domain:*` label per item:

| Label | Applies to |
|---|---|
| `domain:infra` | Kubernetes manifests, Terraform, Ansible, cluster operations |
| `domain:platform` | The project's CLI, MCP servers, core libraries, agent tooling |
| `domain:ops` | Cluster health degradations, incidents, monitoring findings |
| `domain:agents` | Agent topology, skills, orchestration |
| `domain:research` | Pre-implementation option analysis, technology evaluation |
| `domain:docs` | Documentation, runbooks, specs |
| `domain:qa` | Post-deploy verification failures, regression findings |

## Work type classification

After applying a domain label, classify the work type to determine routing:

| Work type | Signal | Route to |
|---|---|---|
| Active incident / degradation | Pod failing, ArgoCD Degraded, node NotReady | Investigator |
| Pre-implementation research | "evaluate options for...", "research...", or `domain:research` label | Researcher |
| Bounded write work | `domain:platform` or `domain:infra`, clear scope, no design needed | Implementer |
| PR opened, no orchestrated plan | Code review needed | Reviewer |
| Multi-step / ambiguous / plan needed | More than one agent needed, unclear scope | Lead |
| Single-agent, well-scoped (non-write) | Obvious owner, bounded non-implementation task | Lead to assign |

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
- Does not re-classify items that already have a `domain:*` label from a previous pass
