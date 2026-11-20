# Changelog

## 0.3.0

- New **`go-public-review`** skill: the go-public criteria for a GitHub
  repository as a checklist — C1 content over all reachable history, commit
  metadata and PR refs (the maintainer's own identity acceptable; credentials,
  employer and colleague names, internal hosts and URLs, and copied private
  content not), C2 branches, tags and PR refs, C3 documentation, C4 CI on a
  public repository, C5 security policy, C6 licence — with the audit method
  (criteria before findings; must-fix, should-fix or acceptable; forward fix
  unless a live exposure cannot be rotated; settings are owner actions) and a
  report shape. Pairs with `github-actions-conventions` for C4.
- README install guidance recommends user-scope installation beside Crew
  (`claude plugin install infra-skills@pixeloven --scope user`), matching
  machine-wide delivery (operator ADR-0019), with project or local scope
  (`enabledPlugins` in the project's `.claude/settings.json` or
  `.claude/settings.local.json`) as the per-repo alternative
  (pixeloven/infra-skills#8, pixeloven/crew#103).

## 0.2.0

Receives the infrastructure material leaving Crew core (pixeloven/crew#102,
roadmap pixeloven/crew#106). Estate facts stay in the consumer's local skills.

### Moved from crew

| From crew | Lands here |
|---|---|
| `pr-review-checklist` Kubernetes checks: control-plane toleration, StorageClass tier, securityContext, `drop: [ALL]`, GPU in overlay, `kubectl kustomize`, PodSecurity levels | **Review checks** in `k8s-kustomize-conventions` (structure, overlays, toleration where `platform-conventions` requires it, GPU, build) and `k8s-workload-patterns` (security context, capabilities, PodSecurity, storage tier, resources) |
| `pr-review-checklist` ExternalSecret checks: registered store, refresh interval, deletion policy, same-change consumer | **Secrets in manifests** in `k8s-workload-patterns`: External Secrets, Sealed Secrets and the CSI driver as examples, invariants deferred to `platform-conventions` |
| `pr-review-checklist` Terraform checks | **Review checks** in `terraform-conventions`. The 1Password provider and `OP_SERVICE_ACCOUNT_TOKEN` go to no skill: they are a consumer `secret-paths` fill |
| `pr-review-checklist` Ansible checks | **Review checks** in `ansible-conventions`. `op run --env-file=…` goes to no skill: it is a consumer `secret-paths` fill |
| `seam-detection` secret-management contract, workload scheduling contract, RBAC grants | New **`infra-seams`** skill, with shapes and greps in `skills/infra-seams/seed-seams.md`. It extends the project's `protected-seams` registry and never fills it |
| `seam-detection` LiteLLM MCP access boundary | `infra-seams`' **LLM or tool-gateway access** shape, named for the capability; LiteLLM's `access_groups` / `allowed_tools` fields are its worked example. No gateway-specific slot is cited |
| `incident-runbook-template` ops-sweep sections (GitOps controller, nodes, pods, ExternalSecrets) and diagnostic commands | New **`k8s-diagnostics`** skill: kubectl node, pod and log commands, GitOps-controller health (Argo CD or Flux, through the capability map's provider or the CLI), secret-sync health, node-OS tooling deferred to `topology`. Talos commands and "ArgoCD via LiteLLM MCP" go to no skill: they are consumer `topology` / `agent-runtime` facts |

Crew keeps the seam method, the finding format and the agent-runtime seam
(`seam-detection`), and the incident report structure and sweep skeleton
(`incident-runbook-template`).

### Other changes

- `k8s-kustomize-conventions` and `ansible-conventions` descriptions now say they
  also apply when reviewing.
- LICENSE copyright holder is now PixelOven.
