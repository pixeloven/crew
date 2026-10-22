---
name: orchard-gh-runs
description: Use when reading a failed GitHub Actions run with the gh CLI in this project, before re-running it or reporting a CI failure, so the failing step's log is read instead of the whole run.
tier: subject
requires: [cli:gh]
---

<!-- crew:learned proposal=2026-10-02-gh-run-logs tool=gh@2.79.0 date=2026-10-02 -->

# orchard-gh-runs

- Read only the failed steps with `gh run view <run-id> --log-failed`; the full log buries them.
