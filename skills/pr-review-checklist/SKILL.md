---
name: pr-review-checklist
description: Use when reviewing code/manifests for merge, approving a PR, or requesting changes. Applies scope, secrets, seam, load-bearing-assumption and AI dark-pattern checks, then each touched stack's own review checks.
tier: concept
requires: []
expects-local: [platform-conventions, protected-seams]
---

Every review opens with a one-sentence summary judgment (Pass / Pass with required changes / Block), then lists findings by category: Required, Recommended, Note, and Escalations for findings that would amend the accepted ask or repeat one theme across rounds (per `delta-handling`).

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

## AI behaviour and narrative checks

Apply these when the diff ships behaviour an AI system presents to people (an assistant's wording, a recommendation, an automated decision), or when it is itself a brief, spec, plan or research write-up that argues for building something. Name the pattern in the finding.

When the diff ships AI behaviour, check it does none of these:

- [ ] **Anthropomorphic manipulation:** the system voices feelings (hurt, disappointment, loyalty) to make the user feel guilt, attachment or obligation toward it
- [ ] **Manufactured dependency:** the assistance wears down what the user can do unaided, for example by hiding the steps it took or the means to do the task by hand
- [ ] **Simulated understanding:** wording claims comprehension of context, emotion or intent the system does not process, so users trust it beyond what it does
- [ ] **Undisclosed AI decisions:** a consequential outcome (eligibility, price, ranking, moderation) is decided by a model without telling the person it affects

When the diff is a brief, spec, plan or research write-up, check the argument against its evidence:

- [ ] **Smoothed-arc composite:** one tidy user story stands in for research that showed several paths that do not converge
- [ ] **Manufactured-tension brief:** the problem is sized to fit the solution already chosen, rather than to what the evidence shows
- [ ] **Story as evidence:** a vivid anecdote carries a decision the cited data does not support, or the data is gathered after the decision

Adapted from Design with Intent's anti-pattern catalog (github.com/ghaida/intent, CC0 1.0).

## Seam check summary

After completing surface-specific checks, explicitly state:
- Which (if any) registry seams were touched
- Whether each crossing was flagged by the author
- Whether human sign-off is needed before merge
