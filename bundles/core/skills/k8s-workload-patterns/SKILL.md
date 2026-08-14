---
name: k8s-workload-patterns
description: Kubernetes workload design patterns — Deployment, StatefulSet, DaemonSet selection, resource limits, health checks, storage tiers, and service exposure. Load when designing or reviewing workload manifests.
tier: subject
requires: []
audience: [crew]
expects-local: [platform-conventions, topology]
---

## Workload type selection

| Type | Use when |
|---|---|
| `Deployment` | Stateless services, multiple replicas, rolling updates |
| `StatefulSet` | Stateful services needing stable network identity or ordered pod management (databases, Valkey) |
| `DaemonSet` | Per-node services (Node Exporter, DCGM Exporter, Traefik in hostNetwork mode) |
| `CronJob` | Scheduled one-off tasks |

For most platform services: `Deployment`. For databases backing platform services: `StatefulSet`.

## Runtime selection

Most workloads use the cluster's default container runtime (no `runtimeClassName` field). One opt-in alternative exists for specific cases — see your platform's conventions skill for the full decision table:

- `runtimeClassName: kata` → workloads running LLM-directed code OR needing real-kernel features (agent surfaces, Docker compose stacks)
- _omit_ → everything else (apps, observability, vault, ARC runners)

## Required fields for all workloads

```yaml
spec:
  template:
    spec:
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
      securityContext:
        fsGroup: 3000        # the project's standard fsGroup — example value; see its conventions skill
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: <app>
          securityContext:
            capabilities:
              drop: [ALL]
```

See your platform's conventions skill for the canonical versions of these fields.

## Resource limits

Always set both `requests` and `limits`. Requests affect scheduling; limits prevent noisy-neighbor OOM:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "512Mi"
```

GPU workloads additionally set `nvidia.com/gpu: 1` in limits (overlay only).

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

Use `readinessProbe` to control traffic routing. Use `livenessProbe` to restart genuinely broken containers. Don't share the same endpoint for both unless the semantics align.

## Service exposure

In-cluster services use `ClusterIP`. External access via Traefik IngressRoute (not plain Ingress):

```yaml
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: <app>
  namespace: <app>
spec:
  entryPoints:
    - websecure
  routes:
    - match: Host(`<app>.<service-domain>`)
      kind: Rule
      services:
        - name: <app>
          port: 8080
```

Application ("lab") services use one wildcard domain; management services use a separate wildcard on the management ingress (a distinct Traefik). The concrete domains live in the consumer's topology skill.

## PersistentVolumeClaims

Always use PVCs, never hostPath (except for DaemonSet node-exporter patterns). StorageClass selection follows the project's storage tiers — typically a runtime tier and a retained tier (e.g. Harmony's `harmony-runtime` / `harmony-storage`):
- runtime tier — databases, model weights, ephemeral workspaces (fast media, Delete reclaim)
- retained tier — user data, media, long-lived shared content (bulk media, Retain reclaim)

Never swap these without reviewing the reclaim consequence.
