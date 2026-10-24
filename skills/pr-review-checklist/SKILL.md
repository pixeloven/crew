---
name: pr-review-checklist
description: Use when reviewing code/manifests for merge, approving a PR, or requesting changes. Applies scope, secrets, seam and load-bearing-assumption checks, then each touched stack's own review checks.
tier: concept
requires: []
expects-local: [platform-conventions, protected-seams]
---

Every review opens with a one-sentence summary judgment (Pass / Pass with required changes / Block), then lists findings by category: Required, Recommended, Note.

When the review is posted to the PR, it starts with the agent marker `🤖 **Agent**:` — on the review body and on every inline comment — so the author can tell agent findings from human ones. Never post an agent review unmarked, and never add the marker to text a human wrote.

## Universal checks (all PRs)

- [ ] PR scope matches stated purpose — no unrelated changes bundled
- [ ] **Load-bearing assumptions listed, and each one falsified against source.** This is the highest-yield check in the list: the common defect is a claim the author asserted but never ground-truthed. If the PR names no assumptions, that is itself a finding — every non-trivial change rests on something.
- [ ] No secrets hardcoded in any changed file (tokens, passwords, API keys)
- [ ] The project's protected-seams registry checked, if it defines one — per `seam-detection`
- [ ] Commit message follows `<type>(<scope>): <subject>` format

## Code

- [ ] The project's lint, format and test gates pass (its `AGENTS.md` or the stack's conventions skill names them)
- [ ] MCP tools: tool descriptions are precise (agents use them for selection)
- [ ] No parallel implementation of a capability that exists in MCP — CLI is a thin wrapper

## Stack checks

For each stack the diff touches (Kubernetes manifests, Terraform, Ansible, CI workflows, a language), apply that stack's conventions skill's review checks. A stack with no conventions skill installed gets the universal checks above plus the project's `platform-conventions`; say in the review that no stack checks were applied.

## Seam check summary

After completing surface-specific checks, explicitly state:
- Which (if any) registry seams were touched
- Whether each crossing was flagged by the author
- Whether human sign-off is needed before merge
