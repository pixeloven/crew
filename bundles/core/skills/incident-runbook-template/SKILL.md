---
name: incident-runbook-template
description: Standard structure for cluster incident reports and ops sweep findings. Load when Investigator is producing a finding, writing a runbook, or filing a GitHub issue for a degradation.
tier: concept
requires: []
audience: [crew]
expects-local: [topology]
---

## Incident report structure

Every finding from Investigator or an ops sweep uses this structure:

```
## Incident: <short title>

**Severity:** Low / Medium / High / Critical
**Status:** Active / Monitoring / Resolved
**Detected:** <timestamp>

### What
Observable symptom. What is the system doing (or not doing)?

### Where
Component, namespace, node, or service. Be specific.

### Why
Root cause or most likely cause. If unknown, state the leading hypothesis and what would confirm it.

### Blast radius
What else is affected or at risk? Downstream dependencies, user-facing impact.

### Recommended action
What should happen next. Not implementation instructions — the action to take.

### Timeline
- <timestamp>: symptom first observed
- <timestamp>: investigation started
- <timestamp>: root cause identified
- <timestamp>: remediation applied / escalated
```

## GitHub issue conventions for findings

When filing a GitHub issue for a persistent degradation:

- **Title:** `[ops] <component>: <symptom>` — e.g., `[ops] <app>: pod CrashLoopBackOff after ESO sync failure`
- **Label:** `domain:ops`
- **Body:** Use the incident report structure above
- **Deduplicate:** Search open issues before filing. If an issue already exists, add a comment with updated observations rather than opening a duplicate.

## Ops sweep output format

For scheduled health sweeps (even clean ones):

```
## Ops Sweep — <date>

**Result:** Clean / <N> issues found

### ArgoCD
- <app>: Healthy ✓
- <app>: Degraded — <reason>

### Kubernetes nodes
- <node>: Ready ✓
- <node>: NotReady — <reason>

### Pods (non-Running)
- <namespace>/<pod>: <status> — <reason>

### ExternalSecrets
- <namespace>/<es>: SecretSynced ✓
- <namespace>/<es>: SecretSyncedError — <reason>

### Issues filed
- #<number>: <title>
```

A clean sweep with no issues still produces output. Silence is not confirmation.

## Diagnostic command reference

```bash
# Node state
kubectl get nodes -o wide
kubectl describe node <node>

# Pod state (non-Running)
kubectl get pods -A | grep -Ev 'Running|Completed'

# ArgoCD via LiteLLM MCP (primary)
# mcp tool: argocd-list_applications
# mcp tool: argocd-get_application

# ArgoCD fallback (CLI)
argocd app list

# ExternalSecrets
kubectl get externalsecret -A
kubectl describe externalsecret -n <ns> <name>

# Node-OS level checks (example: Talos — substitute your node OS's tooling)
talosctl health --nodes <ip>
talosctl logs --nodes <ip> -k   # kernel logs

# Logs
kubectl logs -n <ns> <pod>
kubectl logs -n <ns> <pod> --previous   # crashed container
```
