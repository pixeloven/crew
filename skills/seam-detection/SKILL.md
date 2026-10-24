---
name: seam-detection
description: Use when scanning a diff for protected changes or reviewing widened permissions, secrets, storage, or runtime contracts. Detects registered seam crossings and agent-runtime exit-code changes, and defines the finding format.
tier: concept
requires: []
expects-local: [protected-seams, secret-paths]
---

A seam crossing is any change that touches a protected pattern in the project's seams registry without the crossing having been explicitly flagged by the author. The registry is a **consumer-local** skill; the shapes below are common ones, and a consumer's registry may add or drop entries. This skill defines how to detect crossings in practice.

## Detecting by registry

Read the project's `protected-seams` registry first. Each entry names the protected pattern, the files it lives in, and how to grep for it. For each entry:

1. Run its grep against the changed files (`git diff <base>...HEAD -- <paths>`), not the whole tree.
2. Read every hit in context and decide whether the change alters the protected contract or only touches the file (see False positives).
3. Report each crossing in the finding format below.

A stack pack may seed registry entries for its own shapes (Kubernetes secret sync, scheduling, RBAC, an LLM or tool gateway's access lists); the registry entry, not the pack, is what you scan for. Whatever the registry says, always scan for hardcoded secrets — any string matching key, token, password or API-key patterns — with the project's secret scanner (`gitleaks detect --source . --no-git` is one example) and the `secret-paths` local skill.

## Common shapes

Most registries hold some of these. Each is described by what it protects, not by product:

- **Secret contract** — how secrets reach workloads: which store they come from, how often they refresh, what happens to them on delete, and that each synced secret has a consumer.
- **Scheduling contract** — where workloads may run and on what storage: placement rules, storage tiers, and static-volume bindings.
- **Access boundary** — which callers may reach which tools or services through a gateway: allowlists, access groups, and what an empty list means. An empty list that fails *open* is the crossing to look for first.
- **Runtime contract** — the agent runtime's exit codes, result schema and retry policy (below).
- **Authorization widening** — a grant that lets an identity do more than before: new bindings, new verbs on existing rules, wildcards, escalation-adjacent permissions, broad subjects, or a wider scope where a narrow one would do.

For authorization widening, report the *delta in authority*, not just the diff: what could this identity do after the change that it couldn't before, and what is the worst thing that new permission allows on the named resources? A report-only auditor that gains a delete permission becomes an armed reaper **with no code change**.

### Seam 4 — Agent runtime contract

Only applies where a project runs its own autonomous runtime. The **concrete** contract — which exit codes mean what, the result schema and its path, the retry expression — belongs to that project's agent-runtime local skill; this is the shape to watch for.

**Scan for in diffs:**
- Exit-code semantics changed anywhere the runtime's success/transient/structural distinction is encoded (orchestrator, workflow template, wrapper script)
- The structured result schema — fields added, renamed, or removed — or the path it's written to
- Retry policy decoupled from the exit-code contract (e.g. a retry expression edited, or a duration cap re-introduced)
- Runner image version bumped without a corresponding compatibility check against the orchestrator it hosts

**Shell grep** (adjust the paths to the project's runtime):
```bash
git diff HEAD~1 -- '*orchestrator*' '*[Ww]orkflow*' | grep -E '(exit|retry|[Rr]esult|maxDuration)'
```

## Reporting a seam finding

In a PR comment or review finding:

```
**Seam crossing detected — <seam name>**

File: <path>
Line: <number>
Change: <what changed>
Risk: <why this matters>
Action required: Human sign-off before merge. Tag @<project-approver>.
```

Mark as **Required** in the review. Do not approve or suggest merge until the author acknowledges the crossing and the project approver provides sign-off.

## False positives

Not every touch of a seam-related file is a crossing. Context matters:

- A secret-sync manifest modified to add a label, without touching its store, refresh or delete behaviour, is not a crossing
- A comment or logging change in a runtime orchestrator is not a crossing
- A new test that imports the runtime's result type but doesn't change its schema is not a crossing
- A new grant that only adds read access to resources the identity could already read is worth a Note, not a Required finding

When in doubt, flag it. A false positive costs a brief discussion. A missed crossing can break production.
