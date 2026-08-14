---
name: k8s-kustomize-conventions
description: Kustomize base+overlay structure, overlay patch patterns, manifest validation, and ArgoCD sync conventions. Load when writing or modifying Kubernetes manifests or kustomization files.
tier: subject
requires: []
audience: [crew]
expects-local: [platform-conventions]
---

## Directory structure

Example layout (adapt the root path to the project — the base/overlay split is the convention):

```
infrastructure/kubernetes/
├── base/<component>/       # Reusable base resources (no env-specific config)
└── overlays/prod/<app>/    # Production patches (tolerations, GPU, resources, replicas)
    ├── kustomization.yaml
    └── <patch-files>.yaml
```

ArgoCD syncs each `overlays/prod/<app>/` directory. Base resources are shared — **changes to base manifests propagate to all overlays**. Treat base changes as high blast-radius; prefer overlay patches for environment-specific concerns.

## Required overlay content

On clusters that schedule workloads onto control-plane nodes (check the project's platform conventions skill, e.g. Harmony's `harmony-platform-conventions`), every overlay must include a toleration patch for the control-plane taint:

```yaml
# overlays/prod/<app>/toleration-patch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <app>
spec:
  template:
    spec:
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
```

On such clusters, pods without this toleration will not schedule anywhere.

## kustomization.yaml structure

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base/<component>

patches:
  - path: toleration-patch.yaml
    target:
      kind: Deployment
      name: <app>
```

## GPU workloads

GPU overlays additionally require node affinity and resource limits — applied via overlay patch, never in base:

```yaml
spec:
  template:
    spec:
      nodeSelector:
        kubernetes.io/hostname: <node-name>   # a GPU node — see the project's topology skill
      containers:
        - name: <app>
          resources:
            limits:
              nvidia.com/gpu: 1
```

## Manifest validation

Before opening a PR:
```bash
kubectl kustomize build infrastructure/kubernetes/overlays/prod/<app>
```

This validates the kustomization resolves without error. It does not apply anything to the cluster.

## Static PV shared-asset pattern

To share a read-only asset library (e.g. ML model weights) across namespaces: a dedicated namespace holds static PVs pointing at an NFS export, and each consumer namespace binds a matching RWX PVC with `storageClassName: ""` to bypass dynamic provisioning.

Do not change `storageClassName` on these PVCs — the empty string is intentional to bind to the static PV. The concrete instance (NFS host and path, consuming apps, mount wiring) lives in the project's conventions/topology local skill.

## Kustomize image transforms

Kustomize image transforms do **not** reach WorkflowTemplate CRDs. If pinning an image in a WorkflowTemplate, set the tag directly in the workflow YAML — do not rely on `images:` in `kustomization.yaml` to propagate there.
