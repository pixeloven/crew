---
name: pr-review-checklist
description: Structured checklist for Reviewer to run against PRs across all surface types — Python, K8s manifests, Terraform, Ansible. Load for every pre-merge review.
tier: concept
requires: []
audience: [crew]
expects-local: [platform-conventions, protected-seams]
---

Every review opens with a one-sentence summary judgment (Pass / Pass with required changes / Block), then lists findings by category: Required, Recommended, Note.

## Universal checks (all PRs)

- [ ] PR scope matches stated purpose — no unrelated changes bundled
- [ ] No secrets hardcoded in any changed file (tokens, passwords, API keys)
- [ ] The project's protected-seams registry checked (e.g. `harmony-protected-seams`), if it defines one — per `seam-detection`
- [ ] Commit message follows `<type>(<scope>): <subject>` format

## Python

- [ ] `uv run ruff check` passes (lint)
- [ ] `uv run ruff format --check` passes (formatting)
- [ ] `uv run pytest` passes
- [ ] New public functions/methods have a short docstring (one line, purpose only — no wall-of-text)
- [ ] No `print()` — use `console.print()` (Rich) or logging
- [ ] CLI commands: `typer.Argument` / `typer.Option` with `help=` strings
- [ ] MCP tools: tool descriptions are precise (agents use them for selection)
- [ ] No parallel implementation of a capability that exists in MCP — CLI is a thin wrapper

## Kubernetes manifests

- [ ] Control-plane toleration present in every Deployment/StatefulSet/DaemonSet (see your platform's conventions skill)
- [ ] StorageClass matches data type per the project's conventions skill (e.g. a runtime/ephemeral tier for databases vs a retained tier for user data)
- [ ] Pod security context per the project's conventions skill (e.g. `runAsNonRoot: true`, `seccompProfile: RuntimeDefault`, the project's `fsGroup`)
- [ ] Capabilities: `drop: [ALL]` unless a specific capability is justified
- [ ] No hardcoded secrets — all secrets via ExternalSecret referencing the project's registered ClusterSecretStore
- [ ] ExternalSecrets: `refreshInterval: "0"`, `deletionPolicy: Retain`
- [ ] ExternalSecret has a same-PR consumer (no speculative ESOs)
- [ ] GPU workloads: node selector + `nvidia.com/gpu: 1` in overlay patch, not base
- [ ] `kubectl kustomize build <overlay>` passes without error
- [ ] Namespace PodSecurity levels preserved (some namespaces legitimately require elevated levels — the project's conventions skill says which)

## Terraform

- [ ] `terraform validate` passes
- [ ] No secrets in `.tfvars` or HCL — use 1Password provider or `OP_SERVICE_ACCOUNT_TOKEN`
- [ ] Node IPs defined via inventory/variable indirection (not inline literals)
- [ ] Non-sensitive shared config in `common.tfvars`
- [ ] Changes are idempotent (`terraform plan` on an already-applied state shows no diff)

## Ansible

- [ ] No secrets in playbooks, vars files, or inventory — `op run --env-file=ansible/op.env` pattern
- [ ] `ansible_user` matches the project's inventory convention (its conventions skill says what)
- [ ] Service-management tasks follow the project's documented patterns (some services must not be restarted by Ansible — the conventions skill lists them)
- [ ] Templates mixing bash and Jinja2 have the comment delimiter remap header
- [ ] Playbook is idempotent — safe to run twice

## Seam check summary

After completing surface-specific checks, explicitly state:
- Which (if any) registry seams were touched
- Whether each crossing was flagged by the author
- Whether human sign-off is needed before merge
