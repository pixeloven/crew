---
name: service-deprecation-playbook
description: Pattern for cleanly sunsetting a platform service — data migration, ArgoCD removal, namespace cleanup, DNS, and secret cleanup. Load when removing or decommissioning a service from the platform.
tier: subject
requires: [cluster]
audience: [crew]
---

## Before removing a service

1. **Identify dependents.** Does any other service call this one? Is its data referenced elsewhere? Is there a PVC with user data?
2. **Data disposition.** Decide: migrate, archive, or delete. User-facing data (photos, files, content) must be migrated or archived — never silently deleted.
3. **Grace period.** For user-facing services, communicate the sunset date before removal. For platform-internal services, coordinate with affected consumers.

## Removal sequence

### 1. Disable ingress

Remove or disable the IngressRoute — traffic stops reaching the service. The service continues running.

```bash
kubectl delete ingressroute <name> -n <namespace>
```

Confirm no 200s in access logs before proceeding.

### 2. Scale down

```yaml
spec:
  replicas: 0
```

Or delete the Deployment/StatefulSet directly if the service is being removed entirely.

### 3. Remove from ArgoCD

1. Remove the child Application manifest from `argocd/apps/<app>.yaml`
2. ArgoCD will detect the removed resource on next sync
3. If `prune: true` is set, ArgoCD will delete the in-cluster resources automatically
4. Verify: `argocd app list` should no longer show the app

### 4. Remove K8s manifests

Delete the overlay: `infrastructure/kubernetes/overlays/prod/<app>/` (example layout — adapt to the project's manifest tree)
Delete the base: `infrastructure/kubernetes/base/<app>/` (only if no other overlays reference it)

### 5. Clean up the namespace

Once all workload resources are gone:
```bash
kubectl delete namespace <namespace>
```

PVCs with `Retain` reclaim policy leave orphan PVs behind — manually verify and delete:
```bash
kubectl get pv | grep <namespace>
kubectl delete pv <pv-name>   # after confirming data is migrated/archived
```

### 6. Remove secrets

1. Delete the ExternalSecret (ArgoCD may have already pruned it)
2. Delete the Kubernetes Secret if it persists
3. Archive or delete the 1Password item if it's no longer needed by anything else

### 7. Remove DNS

Remove the DNS record via the project's DNS-as-code path (e.g. a Terraform DNS stage). Preview with `terraform plan` — or the project's infra CLI wrapper, if it ships one — before applying.

### 8. Archive documentation

Archive related knowledge in the vault:
- Service-specific vault notes → tag with `archived` and note the deprecation date

### Post-removal checklist

- [ ] No IngressRoute for the domain
- [ ] No pods running in the namespace
- [ ] Namespace deleted
- [ ] No orphan PVs
- [ ] ExternalSecret and Kubernetes Secret deleted
- [ ] 1Password item archived or deleted
- [ ] DNS record removed
- [ ] ArgoCD no longer shows the app
- [ ] Documentation archived in vault
