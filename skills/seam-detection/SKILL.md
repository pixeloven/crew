---
name: seam-detection
description: How to spot a change that touches a protected pattern and needs human sign-off before merge — detection patterns and greps for ExternalSecret contracts, tolerations and StorageClass selection, MCP access groups, runtime exit-code contracts, and RBAC (ClusterRole, RoleBinding, verb widening, wildcards, escalation-adjacent verbs like escalate/bind/impersonate). Load when scanning a diff for risky changes, or reviewing anything that adds or widens permissions, secrets, storage, or a runtime contract.
tier: concept
requires: []
expects-local: [protected-seams]
---

A seam crossing is any change that touches a protected pattern in the project's seams registry without the crossing having been explicitly flagged by the author. The registry is a **consumer-local** skill (e.g. Harmony's `harmony-protected-seams`); the seams below are the common shapes a registry protects — a consumer's registry may add or drop entries. This skill defines how to detect crossings in practice.

## Detection patterns

### Seam 1 — Secret management contract

**Scan for in diffs:**
- Any `refreshInterval` value other than `"0"` on an ExternalSecret
- `deletionPolicy` changed from `Retain`
- Hardcoded secrets, tokens, passwords, or API keys (any string matching key/token/password patterns)
- ExternalSecret created without a same-PR consumer workload
- `ClusterSecretStore` reference to anything other than the project's registered store (most deployments register exactly one — its name is in the project's secret-paths local skill)

**Shell grep (run against changed files):**
```bash
git diff HEAD~1 | grep -E '(refreshInterval|deletionPolicy|password|token|apiKey|secret)' | grep -v '#'
gitleaks detect --source . --no-git
```

### Seam 2 — Workload scheduling contract

**Scan for in diffs:**
- Deployment, StatefulSet, DaemonSet, or Job with no `tolerations` block
- `tolerations` block missing `node-role.kubernetes.io/control-plane`
- `storageClassName` changed between the project's storage tiers (e.g. a runtime/NVMe class vs a retained/HDD class — names in the project's registry), or to a third class
- `storageClassName: ""` used outside a documented static-PV binding pattern

**Shell grep:**
```bash
git diff HEAD~1 -- '*.yaml' | grep -E '(storageClassName|tolerations)' 
# Then verify control-plane toleration is present in every workload
```

### Seam 3 — LiteLLM MCP access boundary

The load-bearing boundary is the **server `access_groups` ∩ team allowlist ∩ VK groups** intersection (mechanism in the project's gateway-routing local skill; the project's registry names it as a seam), not a VK-vs-MCP credential split.

**Scan for in diffs:**
- A VK's `mcp_access_groups` (or `object_permission`) changed — a consumer's opted-in capability groups widened or narrowed
- A team's allowlist (`object_permission.mcp_access_groups`) changed — the hard ceiling every member VK is capped by
- A server's `access_groups` changed in the LiteLLM proxy config `mcp_servers` block, or a new MCP server added
- A per-server `allowed_tools` allowlist removed or widened
- A group left matching zero servers, or a VK left with no groups (both fail *open* — treated as unrestricted / full-allowlist inheritance)

**Shell grep:**
```bash
git diff HEAD~1 | grep -E '(mcp_access_groups|access_groups|allowed_tools|mcp_servers|object_permission)'
```

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

### RBAC grants (a common fifth shape)

Authorization widening is load-bearing, easy to miss in review, and trivially greppable — it meets the registry bar wherever a project runs Kubernetes RBAC. The canonical case: an auditor workload is report-only *because* its ClusterRole grants only `get`/`list`; adding `delete` to that verb list converts it into an armed reaper **with no code change**.

**Scan for in diffs:**
- New `ClusterRole` / `ClusterRoleBinding` / `Role` / `RoleBinding` manifests, or new `subjects:` on an existing binding
- **Verb widening** on existing `rules:` — especially `delete`, `deletecollection`, `patch`, `update` appearing where only `get`/`list`/`watch` were
- Wildcards: `verbs: ["*"]`, `resources: ["*"]`, `apiGroups: ["*"]`
- **Escalation-adjacent verbs** — `escalate` / `bind` on `roles`/`clusterroles`, `create` on `rolebindings`/`clusterrolebindings`, `impersonate` on users/groups/serviceaccounts
- A binding whose subject is a broad group (`system:authenticated`, `system:serviceaccounts`) rather than a named ServiceAccount
- ClusterRole where a namespaced Role would do — scope creep from namespace to cluster

**Shell grep:**
```bash
git diff HEAD~1 -- '*.yaml' | grep -E '(kind: (Cluster)?Role(Binding)?|^\+.*(verbs|resources|apiGroups|subjects):|\*)'
git diff HEAD~1 | grep -E '^\+.*(escalate|bind|impersonate|deletecollection)'
```

Report the *delta in authority*, not just the diff: what could this identity do after the change that it couldn't before, and what is the worst thing that new verb permits on the named resources?

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

- An ExternalSecret file modified to add a label (not touching `refreshInterval` or `deletionPolicy`) is not a crossing
- A comment or logging change in a runtime orchestrator is not a crossing
- A new test that imports the runtime's result type but doesn't change its schema is not a crossing
- A new `Role` that only adds `get`/`list` on resources the identity could already read is worth a Note, not a Required finding

When in doubt, flag it. A false positive costs a brief discussion. A missed crossing can break production.
