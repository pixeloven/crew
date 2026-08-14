---
name: secret-management-patterns
description: 1Password → ESO → K8s secret flow. Covers ExternalSecret lifecycle, refreshInterval convention, force-sync procedure, and rate limit recovery. Load when creating or modifying ExternalSecrets, rotating credentials, or troubleshooting secret sync.
tier: subject
requires: [cluster]
audience: [crew]
expects-local: [secret-paths]
---

Secrets flow from a single source of truth: **the project's 1Password vault (e.g. Harmony's) → External Secrets Operator → Kubernetes Secret**.

## ExternalSecret conventions

Every ExternalSecret must have:
```yaml
spec:
  refreshInterval: "0"       # sync on creation only — never poll
  deletionPolicy: Retain     # PV-equivalent: secret persists if ES is deleted
```

**Why `refreshInterval: "0"`:** Polling causes 1Password API rate limit cascades across all ESO-managed secrets. This is a hard platform constraint, not a preference.

**ClusterSecretStore:** Reference the project's registered ClusterSecretStore — most deployments register exactly one (e.g. named `onepassword`).

## When to create an ExternalSecret

An ExternalSecret requires a same-PR (or already-deployed) consumer. The ExternalSecret is a bridge from 1Password into Kubernetes — it only earns its keep when a pod mounts or references the resulting Secret.

| Caller | Pattern |
|---|---|
| CLI, CI, agent subprocesses, anything using `op read` | Direct 1Password — `op read 'op://<vault>/<item>/<field>'` |
| Pod / Deployment / CronJob mounting a Secret | ExternalSecret — land both ES and consuming workload in the same PR |

Never create speculative ExternalSecrets ahead of a consumer. A Degraded ES with no consumer generates false-positive ops issues.

## Force-sync procedure

`refreshInterval: "0"` means the standard `force-sync` annotation does nothing. To force a re-sync:

```bash
# 1. Remove finalizers so deletion succeeds
kubectl patch externalsecret <name> -n <ns> --type=merge \
  -p '{"metadata":{"finalizers":[]}}'

# 2. Delete — ArgoCD will recreate from the manifest
kubectl delete externalsecret <name> -n <ns>

# 3. Trigger ArgoCD refresh on the owning app
argocd app get <app-name> --refresh
```

## Rate limit recovery

If ClusterSecretStore shows "rate limit exceeded":

```bash
# Scale ESO to zero — stops all polling and API calls
# (-n external-secrets = the ESO controller namespace; adjust if the project's differs)
kubectl scale deployment/external-secrets -n external-secrets --replicas=0

# Wait 15+ minutes for 1Password rate limit window to clear
# Then restore
kubectl scale deployment/external-secrets -n external-secrets --replicas=1
```

## Credential paths (workstation / non-K8s consumers)

Workstation / CLI consumers read credentials directly from 1Password with `op read 'op://<vault>/<item>/<field>'`. The concrete vault, item, and field for each credential — ArgoCD agent token and break-glass admin password, read-only cluster kubeconfig, cluster-management service-account keys/configs, infra API tokens (hypervisor, storage), and the LiteLLM VK — live in the consumer's secret-management / topology local skill, not here.

**Note:** `LITELLM_API_KEY` carries both LLM routing and MCP scope (`mcp_access_groups`). The MCP gateway rejects unauthenticated requests — MCP client configs send the VK as `Authorization: Bearer ${LITELLM_API_KEY}`; individual tool calls need no extra credentials.

## Runtime credential pattern

```bash
op whoami || { echo "Run 'op signin' first"; exit 1; }

export KUBECONFIG=~/.kube/config
export ARGOCD_SERVER=<argocd-host>                              # your platform's ArgoCD endpoint (topology skill)
export ARGOCD_AUTH_TOKEN=$(op read "op://<vault>/ArgoCD/agent_token")   # concrete op:// path in the consumer's secret-management skill
```

Retrieve only the credentials the task needs. Infrastructure API tokens (e.g. hypervisor or storage-appliance tokens) are only needed by infrastructure status checks.
