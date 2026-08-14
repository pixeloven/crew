---
name: terraform-conventions
description: "Terraform conventions — provider setup (worked example: bpg/proxmox + 1Password), variable structure, staged apply separation, and secret handling. Load when writing or reviewing Terraform configurations."
tier: subject
requires: []
audience: [crew]
expects-local: [secret-paths, topology]
---

## Stage structure

Split infrastructure into ordered stages when later resources depend on earlier ones (management plane before cluster VMs, DNS before services). Example naming (e.g. Harmony uses `stage1-omni` / `stage2-talos`):

```
infrastructure/terraform/
├── stage1-<foundation>/   # e.g. management VM provisioning + DNS
├── stage2-<cluster>/      # e.g. cluster VM provisioning
└── modules/               # Reusable Terraform modules
```

Stages must be applied in order: stage1 → stage2. Destroy in reverse. If the project ships an infra CLI wrapper, it wraps the staging sequence (see below).

## Providers

The worked example stack here is **bpg/proxmox + 1Password** — substitute the project's actual providers; the conventions (API-token auth, secrets resolved at plan/apply time, never on disk) carry over.

**bpg/proxmox** — Proxmox VE API provider. API-only, no SSH required from Terraform.

**1Password** — reads secrets at plan/apply time via `OP_SERVICE_ACCOUNT_TOKEN` env var:
```hcl
data "onepassword_item" "secret" {
  vault = "<your-1password-vault>"
  title = "<item-name>"
}
```

Never hardcode secrets in `.tf` or `.tfvars` files.

## Variable conventions

**Centralized IPs:** All Proxmox node IPs are defined in `variables.tf` under `proxmox_nodes` — never inline literal IPs in resources.

**Shared non-sensitive config:** `common.tfvars` holds infrastructure constants shared across stages (IPs, node names, DNS zone IDs).

```hcl
# variables.tf
variable "proxmox_nodes" {
  type = map(object({
    host = string
    ip   = string
  }))
}
```

## Authentication

- Terraform authenticates to Proxmox via API token (not username/password)
- Secret read at runtime: `OP_SERVICE_ACCOUNT_TOKEN` provides access to the 1Password provider
- DNS provider credentials via the 1Password provider or env vars at apply time

## Idempotency

All Terraform operations must be safe to run repeatedly. `terraform plan` on an already-applied state should show no diff for stable resources. Test with `terraform plan` before `apply`.

## Validation

```bash
terraform validate          # Syntax + schema check (no API calls)
terraform plan              # Show what would change
```

## Commands via the project's infra wrapper (if any)

If the project ships an infra CLI wrapper (e.g. Harmony's `hmy infra`), prefer it — it enforces stage ordering and confirmation prompts. Example shape:

```bash
<cli> infra plan stage1     # terraform plan for stage1
<cli> infra apply stage1    # terraform apply for stage1
<cli> infra plan stage2     # terraform plan for stage2
<cli> infra apply stage2    # terraform apply for stage2
<cli> infra destroy stage2  # Destroy stage2 resources (safe to repeat)
<cli> infra destroy stage1  # Destroy stage1 resources (requires confirmation)
```

Without a wrapper, run `terraform plan` / `terraform apply` per stage directory in the same order.
