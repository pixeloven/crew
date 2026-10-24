---
name: github-repo-workflow
description: Use when editing a GitHub repository, opening or reviewing a PR, or operating on issues. Covers clone → branch → edit → commit → push → PR using pre-wired GH_TOKEN and git credentials.
tier: subject
requires: [external:github]
expects-local: [secret-paths]
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

The GH_TOKEN's scope determines which repos you can reach (read/write). In a deployment's worker images, the token is typically an operator PAT sourced from the deployment's secret manager (the concrete reference belongs in its secret-paths local skill) and scoped to push/issue/PR only for the intended organization.

## Start in the workspace you were given

If a harness, CI job or supervising tool has already prepared a checkout (a worktree, a container checkout, the current directory), work there. A second copy elsewhere is one the host doesn't know about: its work is never reviewed, shipped or cleaned up.

When the host's task contract defines delivery — who commits, pushes or opens the PR, and how — follow it over the steps below, per the reporting contract's *A supervising host's contract wins* rule.

Clone only when no workspace exists. Where the clone goes is the project's choice: check `AGENTS.md` for the canonical clone location and any pre-cloned paths.

```bash
git clone https://github.com/<owner>/<repo> <path>
# or, with the GitHub CLI
gh repo clone <owner>/<repo> <path>
```

## Sync without discarding work

This applies only when starting new work. If the workspace is already on a branch prepared for the task, or the task is to continue an existing branch (such as addressing review comments on a PR), stay on that branch and skip this sync.

An existing checkout may hold uncommitted edits, a stash in progress, or local commits you can't see the value of. Check before you touch it:

```bash
git status --porcelain                    # any output: the tree is dirty
git fetch origin main
git rev-list --count origin/main..HEAD    # non-zero: local commits not on main
```

If the tree is dirty or ahead, **stop and report** what you found; don't stash, reset or discard it. Otherwise branch from the fresh remote main and leave local `main` alone:

```bash
git switch -c <branch> origin/main
# edit files
```

Never `git reset --hard` or `git checkout -- .` to "start fresh". Both discard work with no prompt.

## Name the branch

Use the project's branch convention, from its `AGENTS.md` or a local skill. When it has none, use a prefix matching the change type: `fix/`, `feat/`, `chore/`, `docs/`, `refactor/`.

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

The commands below use the GitHub CLI (`cli:gh`). When it is absent, or the host gives GitHub through another tool, do the same operations through that tool; the steps and the marker rule are unchanged (see `docs/CAPABILITIES.md` in the crew repo).

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

## Mark what the agent writes

Every comment or review the agent posts on a PR or issue starts with a fixed marker, so readers can tell agent output from human output at a glance:

```bash
gh pr comment <N> --body "🤖 **Agent**: <comment>"
```

- **Never post agent output unmarked** — including a draft the operator approved without editing.
- **Never mark human text.** When posting words the operator wrote, post them as theirs; mark only the agent's own additions.
- Commits, titles and PR or issue bodies keep the project's own format and attribution convention; the marker is for comments and reviews.

## Iterate on review

```bash
gh pr view <N>                            # description + state + conversation
gh pr checks <N>                          # CI status rollup
gh pr view <N> --json reviews,comments    # programmatic check
gh pr comment <N> --body "🤖 **Agent**: ..."  # post a top-level comment (marked)
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
gh issue comment <N> --body "🤖 **Agent**: ..."  # update with progress (marked)
gh issue edit <N> --add-label <label>     # routing labels (e.g. `agent:queued`)
gh issue close <N> --reason completed     # close with a reason
```

## What not to do

- **Don't `git reset --hard`** an existing checkout. When starting new work there, if it is dirty or ahead of `origin/main`, stop and report.
- **Don't `--no-verify`** to skip pre-commit hooks. Hooks catch secrets, formatting, and lint issues — investigate failures, don't bypass.
- **Don't `git add -A`** in repos with untracked files you didn't create. Add specific paths.
- **Don't force-push** a branch with reviews unless rebase is the explicit intent. Push new commits instead.
- **Don't commit secrets**. Treat `.env`, `*.key`, and anything with `secret` in its name as suspect.
- **Don't embed `GH_TOKEN` in URLs or commit messages.** The credential helper handles auth invisibly.
