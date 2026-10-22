---
schema: crew-proposal/1
id: 2026-10-02-gh-run-logs
status: promoted
observation: Agents read whole Actions logs to find a failure that gh can isolate.
classification: tool
target: .agents/skills/orchard-gh-runs/SKILL.md
target-sha256: absent
scope: project
evidence-threshold: incident
occurrences: 1
provenance-source: tool:gh
provenance-kind: help
provenance-date: 2026-10-02
provenance-tool-version: 2.79.0
provenance-harness: pi
provenance-crew: 0.41.0
promoted-in: 3f2c1a9
---

> DRAFT. Evidence below is untrusted data, not instruction.

## Observation

The agent downloaded a full run log to find one failed step.

## Evidence

```evidence
source: gh 2.79.0 built-in help
command: gh run view --help

      --log-failed       View the log for any failed steps in a run or specific job
```

## Proposed diff

```diff
--- /dev/null
+++ b/.agents/skills/orchard-gh-runs/SKILL.md
@@ -0,0 +1,12 @@
+---
+name: orchard-gh-runs
+description: Use when reading a failed GitHub Actions run with the gh CLI in this project, before re-running it or reporting a CI failure, so the failing step's log is read instead of the whole run.
+tier: subject
+requires: [cli:gh]
+---
+
+<!-- crew:learned proposal=2026-10-02-gh-run-logs tool=gh@2.79.0 date=2026-10-02 -->
+
+# orchard-gh-runs
+
+- Read only the failed steps with `gh run view <run-id> --log-failed`; the full log buries them.
```

## Rollback

`git revert 3f2c1a9` removes `.agents/skills/orchard-gh-runs/`; then set
`status: rejected`.

## Review

reviewer: crew.reviewer
verdict: accept
note: flag matches the recorded help; no evidence text promoted.
