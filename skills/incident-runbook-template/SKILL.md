---
name: incident-runbook-template
description: Use when writing an incident report, diagnosis brief, degradation issue, health sweep, or repeatable runbook. Structures what broke, where, why, blast radius, recommended action, and confidence.
tier: concept
requires: []
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

- **Title:** `[ops] <component>: <symptom>` — e.g., `[ops] <app>: pod CrashLoopBackOff after secret sync failure`
- **Label:** `domain:ops`
- **Body:** Use the incident report structure above
- **Deduplicate:** Search open issues before filing. If an issue already exists, add a comment with updated observations rather than opening a duplicate.

## Ops sweep output format

For scheduled health sweeps (even clean ones), write one section per component the project's `topology` local skill names, in the order it lists them:

```
## Ops Sweep — <date>

**Result:** Clean / <N> issues found

### <component>
- <item>: Healthy ✓
- <item>: Degraded — <reason>

### <component>
- <item>: Healthy ✓

### Issues filed
- #<number>: <title>
```

How to check each component — the commands, MCP tools, or dashboards — comes from the stack's diagnostics skill and the project's own runbooks, not from this template.

A clean sweep with no issues still produces output. Silence is not confirmation.
