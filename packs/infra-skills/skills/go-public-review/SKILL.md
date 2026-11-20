---
name: go-public-review
description: Use before making a GitHub repository public, or when reviewing a public one. Audits history, commit metadata and PR refs for exposed content, plus branch and tag rules, docs, public CI, security policy and licence; grades each finding.
tier: concept
requires: [external:github, plugin:crew@>=0.38.0]
---

A go-public review decides whether a repository may be public, or, for one
that already is, what published material must be fixed, removed or rotated.
It is a checklist with evidence, not a feeling. The review reads and reports;
it never changes repository settings, rewrites history or rotates credentials
itself.

## Method

1. **Criteria before findings.** Start from written criteria: the project's own
   recorded go-public decision if it has one, otherwise the checklist below.
   Record any project amendment (an approved exception, a different licence)
   before the audit starts, never to fit a finding afterwards.
2. **Audit everything reachable.** Every commit reachable from any branch, tag
   or `refs/pull/*` ref; commit metadata (author and committer names and
   emails, trailers) as well as content; PR, issue, release and comment text;
   committed binaries and screenshots. The forge keeps PR refs after a branch
   is deleted, and only its support can remove them.
3. **Classify each finding** as **must-fix now** (a live exposure),
   **should-fix** (a forward fix before or soon after publishing) or
   **acceptable** (with the reason recorded).
4. **Forward fix by default.** Fix the current tree, add a control, rotate the
   credential. Rewrite history only for a live exposure that cannot be rotated:
   a rewrite breaks forks, published tags and any upstream merge base, and it
   cannot reach PR refs, forks or mirrors.
5. **Settings are owner actions.** Branch protection, rulesets, security
   features and Actions settings (C2, C4, C5) go in the report as actions for
   the repository owner, with the exact setting. The review never applies them.

Never copy a finding's sensitive value into the report: give its location
(commit, path, line, PR number) and redact the value.

## Criteria

### C1 — Content, over all reachable history

- [ ] No credentials. A live one is must-fix now: rotate first, then decide on
      history. A rotated or fake one is acceptable once allowlisted in the
      secret scanner with a reason.
- [ ] No employer or client names in files, docs, or PR, issue, release and
      comment text.
- [ ] No colleague names or contact details.
- [ ] No internal host names, IP addresses, internal URLs or SaaS tenant URLs.
- [ ] No content copied from private references. A bare link to a private
      repository is should-fix in mutable docs and acceptable in immutable
      records (accepted decision records, merged PR text, commit messages).
- [ ] The maintainer's own identity is the one exception: their names and email
      addresses, work and personal, are acceptable, including an employer email
      domain in commit metadata. This does not extend to colleagues.

### C2 — Branches, tags and PR refs

- [ ] Every non-default branch is open work with a live PR or a documented
      long-lived branch; merged and abandoned branches are deleted.
- [ ] Release tags are protected against deletion and force-update; releases
      are immutable where the plan allows.
- [ ] The default branch is protected: no force push, no deletion, changes
      through PRs, required status checks.

### C3 — Documentation

- [ ] README, LICENSE, NOTICE and CONTRIBUTING are present and accurate for an
      outside reader.
- [ ] Links in mutable docs resolve for an anonymous reader, or are marked
      private.
- [ ] Operational detail (host roles, provisioning paths, personal machine
      configuration) is described generically unless it is the document's
      subject.

### C4 — CI on a public repository

Pairs with `github-actions-conventions`, whose review of each workflow covers
pinning, permissions and secret access.

- [ ] Untrusted PR code never reaches private infrastructure: no self-hosted or
      private runner labels on PR-triggered jobs, and no `pull_request_target`
      job that checks out the PR head.
- [ ] The workflow token defaults to read-only; each workflow declares
      least-privilege `permissions:`, and only release jobs get
      `contents: write`.
- [ ] No repository or environment secrets are reachable from PR-triggered jobs.
- [ ] Fork-PR workflows need maintainer approval for outside contributors.
- [ ] A sample of public Actions logs and artifacts is checked for leaks.

### C5 — Security policy

- [ ] `SECURITY.md` names a private reporting channel, and private
      vulnerability reporting is enabled.
- [ ] Secret scanning and push protection are enabled, in addition to any
      in-workflow secret scan.
- [ ] Dependabot alerts and code scanning are enabled where a supported
      language or Actions workflows exist.

### C6 — Licence

- [ ] The licence file matches the declared licence (package manifests, README).
- [ ] Upstream copyright notices are retained, and NOTICE attributes upstream
      and third-party components accurately.

## Evidence commands

All read-only. `<owner>/<repo>` is the repository under review.

```bash
# C1: bring PR refs local, then scan and list identities across all of them
git fetch origin '+refs/pull/*/head:refs/remotes/origin/pr/*'
gitleaks git --log-opts="--all"
git log --all --format='%an <%ae>%n%cn <%ce>' | sort -u
git log --all --format='%(trailers:only)' | sort -u
git log --all -p -G'<pattern>'              # names, hosts, domains from the criteria
gh pr list -R <owner>/<repo> --state all --limit 10000 --json number,title,body,reviews
gh issue list -R <owner>/<repo> --state all --limit 10000 --json number,title,body
gh api --paginate repos/<owner>/<repo>/releases --jq '.[] | {tag_name, name, body}'
gh api --paginate repos/<owner>/<repo>/issues/comments --jq '.[] | {html_url, body}'
gh api --paginate repos/<owner>/<repo>/pulls/comments --jq '.[] | {html_url, body}'
gh api --paginate repos/<owner>/<repo>/comments --jq '.[] | {html_url, body}'

# C2, C4, C5: current settings, reported, never changed
gh api --paginate repos/<owner>/<repo>/branches       # each non-default branch
gh api --paginate repos/<owner>/<repo>/rulesets
gh api repos/<owner>/<repo>/branches/<default>/protection
gh api repos/<owner>/<repo>/actions/permissions/workflow
gh api repos/<owner>/<repo>/private-vulnerability-reporting
gh api repos/<owner>/<repo> --jq '.security_and_analysis'
```

## Report

- **Criteria:** their source and any recorded amendments or exceptions.
- **Scope:** refs and commit range audited, the date, and anything not reached.
- **Verdict per criterion:** pass, fail, or pass with a recorded exception.
- **Findings:** one row each — criterion, classification, location (redacted),
  fix: forward fix, rotation, or history rewrite with its justification.
- **Owner actions:** each setting change, with the exact setting and value.

The repository may be public, or stay public, only when every criterion passes
or carries an owner-approved exception.
