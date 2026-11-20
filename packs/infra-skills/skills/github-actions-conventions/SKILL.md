---
name: github-actions-conventions
description: Use when writing or reviewing GitHub Actions workflows or CI. Covers workflow structure, action pinning, secret access, gh CLI usage, uv-based Python jobs, gitleaks scanning, and automated-commit patterns.
tier: subject
requires: [external:github, plugin:crew@>=0.38.0]
expects-local: [secret-paths]
---

## Auth model

GitHub Actions workflows authenticate via `GH_TOKEN` (automatically provided as `GITHUB_TOKEN`). For operations needing broader scope (workflow file changes, package publishing), use the repo's configured token. Set a top-level `permissions:` block and grant each job only what it needs.

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

permissions:
  contents: read

jobs:
  <job-name>:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<commit-sha> # vX
      - name: <step>
        run: <command>
```

Pin third-party actions to a full commit SHA with the version in a trailing comment; a tag can be moved under you.

## Python workflows

Use `uv` for Python setup — faster than pip, consistent with local development:

```yaml
- name: Install uv
  uses: astral-sh/setup-uv@<commit-sha> # vX

- name: Install dependencies
  run: uv sync

- name: Lint
  run: uv run ruff check

- name: Test
  run: uv run pytest
```

## Secret management in CI

Secrets come from GitHub Actions secrets (repository, environment, or organization level). When the project keeps secrets in an external manager, prefer the manager's official action or OIDC federation over a long-lived token; if a token is unavoidable, store it as one Actions secret and resolve everything else through it. Which manager and which paths the project uses belong in its secret-paths local skill, if it defines one.

Never hardcode tokens, passwords, or API keys in workflow files. Use `${{ secrets.SECRET_NAME }}` for all credentials.

## gitleaks

Pre-commit secret scanning via gitleaks prevents accidental secret commits. In CI, run as a step on PRs:

```yaml
- name: Secret scan
  uses: gitleaks/gitleaks-action@<commit-sha> # v2
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
