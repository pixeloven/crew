---
name: github-repo-workflow
description: Clone, edit, commit, push, and PR-create against any GitHub repo using git and gh. Auth is already wired via GH_TOKEN + gh credential helper — no setup required. Load when a task involves editing files in a GitHub repo, opening or reviewing a PR, or operating on issues.
tier: subject
requires: [external:github]
audience: [crew]
---

# GitHub Repo Workflow

When a task requires editing a GitHub repo (manifests, configs, code), follow this end-to-end pattern: clone → branch → edit → commit → push → PR.

## Auth is already wired

You don't need to set up credentials. The environment provides:

- `GH_TOKEN` env var (mounted from a 1Password Secret)
- `gh` CLI installed and authenticated against `GH_TOKEN`
- git's credential helper for `https://github.com` set to `gh auth git-credential` system-wide (`/etc/gitconfig`)
- `safe.directory = *` set system-wide so cloned repos don't trigger ownership warnings

Plain `git clone https://github.com/...` and `gh repo clone owner/repo` both authenticate transparently. Never embed tokens in remote URLs.

The GH_TOKEN's scope determines which repos you can reach (read/write). In a deployment's worker images, the token is typically an operator PAT (e.g. Harmony's pi-web/pi-worker) sourced from 1Password (concrete `op://<vault>/<item>/<field>` path in the consumer's secret-management local skill) — scoped to push/issue/PR on the deployment's GitHub org (`<org>/*`).

## When the repo isn't on disk

Clone it. Default to a path under the home directory: `~/<repo>`.

```bash
git clone https://github.com/<owner>/<repo> ~/<repo>
# or
gh repo clone <owner>/<repo> ~/<repo>
```

When the repo IS already on disk and you're starting fresh work, sync to current main:

```bash
cd ~/<repo>
git fetch origin main
git checkout main
git reset --hard origin/main
```

## Branch + edit

Use a conventional prefix matching the change type — `fix/`, `feat/`, `chore/`, `docs/`, `refactor/`.

```bash
git checkout -b fix/short-description
# edit files
```

## Commit

Stage specific files, not the entire tree (`git add -A` can sweep in untracked content you didn't author).

```bash
git add path/to/file1 path/to/file2
git commit -m "$(cat <<'EOF'
<type>(<scope>): <subject>

<optional body — why this change, not what>
EOF
)"
```

The heredoc form preserves multi-line formatting and avoids shell-escape hazards in the message body.

## Push the branch

```bash
git push -u origin <branch>
```

## Open the PR

```bash
gh pr create --title "<type>(<scope>): <subject>" --body "$(cat <<'EOF'
## Summary
- <bullet>
- <bullet>

## Why
<one paragraph rationale>

## Test plan
- [ ] <verification step>
- [ ] <verification step>
EOF
)"
```

The PR URL is printed on stdout — capture it from the command output if you need to reference it in subsequent steps.

## Iterate on review

```bash
gh pr view <N>                            # description + state + conversation
gh pr checks <N>                          # CI status rollup
gh pr view <N> --json reviews,comments    # programmatic check
gh pr comment <N> --body "..."            # post a top-level comment
gh api repos/<owner>/<repo>/pulls/<N>/comments  # inline review comments
```

For continuing work on an existing PR (e.g., addressing review feedback):

```bash
gh pr checkout <N>                        # local-checkout the PR's branch
# edit, git add, git commit
git push                                  # pushes to the PR's branch
```

## Issues

```bash
gh issue create --title "..." --body "$(cat <<'EOF'
...
EOF
)" --label <label1>,<label2>

gh issue view <N>                         # full body + labels + state
gh issue comment <N> --body "..."         # update with progress
gh issue edit <N> --add-label <label>     # routing labels (e.g. `agent:queued`)
gh issue close <N> --reason completed     # close with a reason
```

## What not to do

- **Don't `--no-verify`** to skip pre-commit hooks. Hooks catch secrets, formatting, and lint issues — investigate failures, don't bypass.
- **Don't `git add -A`** in repos with untracked files you didn't create. Add specific paths.
- **Don't force-push** a branch with reviews unless rebase is the explicit intent. Push new commits instead.
- **Don't commit secrets**. Treat `.env`, `*.key`, and anything with `secret` in its name as suspect.
- **Don't embed `GH_TOKEN` in URLs or commit messages.** The credential helper handles auth invisibly.

## Project-specific clone path

For the active project, check `AGENTS.md` for the canonical clone location and any pre-cloned paths — each consumer documents its own repo and clone convention there.
