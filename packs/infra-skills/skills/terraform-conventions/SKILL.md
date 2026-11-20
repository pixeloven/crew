---
name: terraform-conventions
description: Use when writing or reviewing Terraform or OpenTofu. Defines staged-apply separation, provider and version pinning, variable structure, secret resolution at plan/apply time, and idempotent plan-before-apply discipline.
tier: subject
requires: [plugin:crew@>=0.38.0]
expects-local: [platform-conventions, secret-paths, topology]
---

## Stage structure

Split infrastructure into ordered stages when later resources depend on earlier ones (management plane before cluster VMs, DNS before services). Example naming:

```
infrastructure/terraform/
├── stage1-<foundation>/   # e.g. management VM provisioning + DNS
├── stage2-<cluster>/      # e.g. cluster VM provisioning
└── modules/               # Reusable Terraform modules
```

Stages must be applied in order: stage1 → stage2. Destroy in reverse. Each stage keeps its own state; a later stage reads an earlier one through outputs or data sources, never by copying values. If the project ships an infra CLI wrapper, it wraps the staging sequence (see below).

## Providers

Which providers the project uses — compute, DNS, secrets — is an estate choice, recorded in the project's platform-conventions local skill, if it defines one. These conventions hold for any provider:

- **Pin versions.** Declare every provider in `required_providers` with a version constraint, and commit `.terraform.lock.hcl`. Upgrade deliberately, in its own change.
- **Token auth, not passwords.** Authenticate with a scoped API token or workload identity — never a human username/password in provider config.
- **Prefer API-only providers.** A provider that also needs SSH or an agent on the target adds a second credential and a second failure mode; accept that only when the API cannot do the job.
- **Credentials from the environment.** Provider credentials arrive at plan/apply time through env vars or a secrets-manager data source — never as literals in `.tf` or `.tfvars`.

## Secrets

Secrets are resolved at plan/apply time and never written to disk in the repo. Two common shapes:

- a secrets-manager provider data source that reads an item by reference;
- env vars injected by a wrapper that resolves references at invocation time.

```hcl
data "<secrets_provider>_item" "db" {
  # reference only — the concrete store, item, and field come from the
  # project's secret-paths local skill, if it defines one
}
```

Never hardcode secrets in `.tf` or `.tfvars` files. Mark secret-bearing variables and outputs `sensitive = true`, and remember that values read this way still land in state: the state backend must be encrypted and access-controlled. Which secrets backend, store names, and item paths the project uses belong in its secret-paths local skill, not here.

## Variable conventions

**Centralized addresses:** host and node addresses are defined once, in a typed map variable — never inline literal IPs in resources.

**Shared non-sensitive config:** a `common.tfvars` (or equivalent) holds infrastructure constants shared across stages (addresses, node names, DNS zone IDs). The concrete values are the project's topology.

```hcl
# variables.tf
variable "nodes" {
  type = map(object({
    host = string
    ip   = string
  }))
}
```

Give every variable a `type` and a `description`; add a `validation` block where a bad value would otherwise fail late, at apply.

## Idempotency

All Terraform operations must be safe to run repeatedly. `terraform plan` on an already-applied state should show no diff for stable resources. A plan that always shows a diff is a bug to fix (usually a provider default to set explicitly, or a computed attribute for `ignore_changes`), not noise to accept. Run `terraform plan` before `apply`.

## Validation

```bash
terraform fmt -check        # Formatting
terraform validate          # Syntax + schema check (no API calls)
terraform plan              # Show what would change
```

## Commands via the project's infra wrapper (if any)

If the project ships an infrastructure CLI wrapper, prefer it — it enforces stage ordering and confirmation prompts. Example shape:

```bash
<cli> infra plan stage1     # terraform plan for stage1
<cli> infra apply stage1    # terraform apply for stage1
<cli> infra plan stage2     # terraform plan for stage2
<cli> infra apply stage2    # terraform apply for stage2
<cli> infra destroy stage2  # Destroy stage2 resources (safe to repeat)
<cli> infra destroy stage1  # Destroy stage1 resources (requires confirmation)
```

Without a wrapper, run `terraform plan` / `terraform apply` per stage directory in the same order.

## Review checks

- [ ] `terraform fmt -check` and `terraform validate` pass for every stage the change touches
- [ ] No secrets in `.tf` or `.tfvars`; credentials resolve at plan/apply time through the project's secrets path (its secret-paths local skill names which)
- [ ] Secret-bearing variables and outputs are `sensitive = true`
- [ ] Host and node addresses come from the typed address map, not inline literals
- [ ] Shared non-sensitive constants live in the shared tfvars, not repeated per stage
- [ ] New providers are pinned in `required_providers` and `.terraform.lock.hcl` is committed
- [ ] The change is idempotent: a plan against already-applied state shows no diff for stable resources
- [ ] Stage order is respected: a later stage reads an earlier one through outputs or data sources, never copied values
