---
name: k8s-service-onboarding
description: Step-by-step pattern for adding a new service to the platform — namespace, manifests, ArgoCD app, secrets, ingress, and verification. Load when deploying a new application to the cluster.
tier: subject
requires: [cluster]
audience: [crew]
expects-local: [platform-conventions, topology, secret-paths]
---

## Onboarding checklist

This skill is the step-by-step expansion of `argocd-deployment-patterns` § "Adding a new service" — that section owns the registration model (root Application, sync waves); follow this one when actually onboarding. Repo paths below follow the example layout in `k8s-kustomize-conventions`; adapt to the project.

### 1. Namespace and PodSecurity

Create a namespace with PodSecurity labels:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: <app>
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/warn: baseline
```

Use `privileged` only if the workload requires hostNetwork, hostPID, or hostPath (like node exporters). Default is `baseline`.

### 2. Base manifests

Create `infrastructure/kubernetes/base/<app>/`:
- `deployment.yaml` (or StatefulSet)
- `service.yaml`
- `configmap.yaml` (if needed)
- `kustomization.yaml`

All workload resources must include the control-plane toleration and standard security context — see your platform's conventions skill.

### 3. Overlay

Create `infrastructure/kubernetes/overlays/prod/<app>/`:
- `kustomization.yaml` — references base, includes patches
- `toleration-patch.yaml` — control-plane toleration on the workload
- GPU patch if needed (node selector + `nvidia.com/gpu: 1`)

### 4. Secrets

If the service needs secrets from 1Password:
1. Add the 1Password item to the project's secret vault
2. Create an ExternalSecret in the app namespace — only if a pod consumer exists in the same PR
3. Reference the project's registered ClusterSecretStore
4. Set `refreshInterval: "0"` and `deletionPolicy: Retain`

See `secret-management-patterns` for the full ESO pattern.

### 5. Ingress

Add a Traefik IngressRoute if the service needs external access:

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: <app>
  namespace: <app>
spec:
  entryPoints: [websecure]
  routes:
    - match: Host(`<app>.<service-domain>`)
      kind: Rule
      services:
        - name: <app>
          port: 8080
```

Add a DNS A record (via the platform's DNS/Terraform stage) pointing `<app>.<service-domain>` to the cluster node IPs. The concrete service domain, DNS stage, and node IPs live in the consumer's topology skill.

### 6. ArgoCD child Application

Create `infrastructure/kubernetes/argocd/apps/<app>.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: <app>
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/<your-org>/<repo>.git
    targetRevision: HEAD
    path: infrastructure/kubernetes/overlays/prod/<app>
  destination:
    server: https://kubernetes.default.svc
    namespace: <app>
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 7. Validation

```bash
kubectl kustomize build infrastructure/kubernetes/overlays/prod/<app>
# Review output for correctness before committing
```

After merge and ArgoCD sync:
```bash
argocd app get <app>
kubectl get pods -n <app>
kubectl get externalsecret -n <app>   # if secrets exist
```

### 8. Record the service

Register the new service in the project's service inventory (per its conventions local skill) so future health sweeps and the deprecation playbook can find it.
