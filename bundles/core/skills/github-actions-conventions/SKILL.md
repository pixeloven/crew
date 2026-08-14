---
name: github-actions-conventions
description: GitHub Actions workflow conventions — workflow structure, secret access, gh CLI usage, uv-based Python CI, gitleaks scanning, and automated-commit patterns. Load when writing or reviewing GitHub Actions workflows or CI pipelines.
tier: subject
requires: [external:github]
audience: [crew]
---

## Auth model

GitHub Actions workflows authenticate via `GH_TOKEN` (automatically provided as `GITHUB_TOKEN`). For operations needing broader scope (workflow file changes, package publishing), use the repo's configured token.

The `gh` CLI is pre-installed in GitHub-hosted runners. Use `gh` for all GitHub API operations — never raw curl to the GitHub API unless `gh` can't do it.

```yaml
env:
  GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Workflow structure

```yaml
name: <workflow-name>

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  <job-name>:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: <step>
        run: <command>
```

## Python workflows

Use `uv` for Python setup — faster than pip, consistent with local development:

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@v3

- name: Install dependencies
  run: uv sync

- name: Lint
  run: uv run ruff check

- name: Test
  run: uv run pytest
```

## Secret management in CI

Secrets come from GitHub Actions secrets (repository or organization level). For 1Password-backed secrets, use the 1Password GitHub Actions integration or pass `OP_SERVICE_ACCOUNT_TOKEN` as a secret.

Never hardcode tokens, passwords, or API keys in workflow files. Use `${{ secrets.SECRET_NAME }}` for all credentials.

## gitleaks

Pre-commit secret scanning via gitleaks prevents accidental secret commits. In CI, run as a step on PRs:

```yaml
- name: Secret scan
  uses: gitleaks/gitleaks-action@v2
  env:
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Commit conventions in CI

Automated commits from CI (e.g., version bumps, changelog updates) use the same commit format:
```
<type>(<scope>): <subject> [skip ci]
```

Use `[skip ci]` to prevent CI loops on automated commits.

## gh CLI patterns

```bash
# Create PR
gh pr create --title "..." --body "..."

# Comment on issue
gh issue comment 42 --body "..."

# Apply label
gh issue edit 42 --add-label "domain:ops"

# Check PR status
gh pr view 42 --json state,mergeable

# Merge PR
gh pr merge 42 --squash --auto
```
