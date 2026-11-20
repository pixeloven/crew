---
name: k8s-workload-patterns
description: Use when writing or reviewing a Kubernetes workload, choosing Deployment vs StatefulSet vs DaemonSet vs Job, or sizing a pod. Covers resources, probes, storage, security context, runtime class, and exposure.
tier: subject
requires: [plugin:crew@>=0.38.0]
expects-local: [platform-conventions, topology]
---

## Workload type selection

| Type | Use when |
|---|---|
| `Deployment` | Stateless services, multiple replicas, rolling updates |
| `StatefulSet` | Stateful services needing stable network identity or ordered pod management (databases, Valkey/Redis) |
| `DaemonSet` | Per-node services (node exporters, GPU exporters, a hostNetwork ingress controller) |
| `Job` | Run-to-completion tasks |
| `CronJob` | Scheduled one-off tasks |

For most platform services: `Deployment`. For databases backing platform services: `StatefulSet`.

## Runtime selection

Most workloads use the cluster's default container runtime (no `runtimeClassName` field). A cluster may offer an opt-in sandboxed `RuntimeClass` (e.g. Kata Containers or gVisor) for workloads that run untrusted or LLM-directed code, or that need real-kernel features without host privileges. Which classes exist and the decision table for using them belong in the project's platform-conventions local skill, if it defines one; without one, omit `runtimeClassName`.

## Baseline pod spec

```yaml
spec:
  template:
    spec:
      securityContext:
        fsGroup: <project-fsGroup>   # see the project's platform-conventions local skill
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: <app>
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: [ALL]
```

This meets the `restricted` Pod Security Standard. On clusters that schedule onto control-plane nodes, add the control-plane toleration as well (see `k8s-kustomize-conventions`). The project's platform-conventions local skill, if it defines one, holds the canonical versions of these fields.

## Resource limits

Always set `requests`, and set memory `limits`. Requests affect scheduling; memory limits prevent noisy-neighbour OOM on the node:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "512Mi"
```

GPU workloads additionally set `nvidia.com/gpu: 1` (or the vendor's resource name) in limits — overlay only.

## Health checks

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8080
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /ready
    port: 8080
  initialDelaySeconds: 5
  periodSeconds: 5
```

Use `readinessProbe` to control traffic routing. Use `livenessProbe` to restart genuinely broken containers. Don't share the same endpoint for both unless the semantics align. Slow starters get a `startupProbe` rather than a long liveness delay.

## Service exposure

In-cluster services use `ClusterIP`. External access goes through the cluster's ingress layer — standard `Ingress`, Gateway API `HTTPRoute`, or a controller-specific CRD (e.g. Traefik `IngressRoute`). Which one, which entry points, and which hostnames are estate choices: follow the project's platform-conventions local skill, if it defines one, and don't mix mechanisms within one cluster without reason.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: <app>
  namespace: <app>
spec:
  parentRefs:
    - name: <gateway>
  hostnames:
    - <app>.<service-domain>
  rules:
    - backendRefs:
        - name: <app>
          port: 8080
```

Clusters often separate application and management traffic onto different domains or ingress instances. The concrete domains live in the project's topology local skill, if it defines one.

## PersistentVolumeClaims

Always use PVCs, never hostPath (except for node-level DaemonSet patterns such as exporters). StorageClass selection follows the project's platform-conventions local skill — typically separate runtime and retained tiers:
- runtime tier — databases, model weights, ephemeral workspaces (fast media, `Delete` reclaim)
- retained tier — user data, media, long-lived shared content (bulk media, `Retain` reclaim)

Never swap these without reviewing the reclaim consequence.

## Secrets in manifests

A manifest never holds a secret value. It holds a **secret-sync object** that a controller resolves into a Kubernetes `Secret` from the project's secret store. Common shapes:

- **External Secrets Operator:** an `ExternalSecret` referencing a `ClusterSecretStore` or `SecretStore`, with a refresh interval and a deletion policy.
- **Sealed Secrets:** a `SealedSecret` encrypted for one cluster's controller key, committed as ciphertext.
- **Secrets Store CSI driver:** a `SecretProviderClass` mounted as a volume, optionally synced to a `Secret`.

Which mechanism the project uses, its registered store name, and the invariants that must never change silently (for External Secrets, typically the refresh interval and the deletion policy) belong to its platform-conventions local skill, if it defines one; store and item paths belong to its secret-paths local skill. Without them, ask rather than pick values. Add a sync object in the same change as the workload that consumes it, never ahead of it. Changes to these invariants are seam material: see `infra-seams`.

## Review checks

When reviewing a workload manifest (with `k8s-kustomize-conventions` for structure and overlays):

- [ ] Pod and container `securityContext` match the project's platform-conventions local skill, if it defines one (`runAsNonRoot: true`, `seccompProfile: RuntimeDefault`, its `fsGroup`, `allowPrivilegeEscalation: false`)
- [ ] `capabilities: drop: [ALL]`, with any added capability justified in the change
- [ ] Namespace PodSecurity levels (`pod-security.kubernetes.io/*` labels) are preserved; a namespace raised above `restricted` is one the platform-conventions skill names
- [ ] StorageClass matches the data's tier, and a tier change is reviewed for its reclaim consequence
- [ ] `requests` set, memory `limits` set; GPU resources only in an overlay
- [ ] Probes match the workload's real readiness and liveness semantics
- [ ] No secret values in any manifest; secrets arrive through the project's sync object, referencing its registered store, with a consumer in the same change (see Secrets in manifests)
- [ ] `runtimeClassName` only where the platform-conventions skill's decision table calls for it
