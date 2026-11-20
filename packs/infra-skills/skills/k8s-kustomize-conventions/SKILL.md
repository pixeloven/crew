---
name: k8s-kustomize-conventions
description: Use when writing, changing or reviewing Kubernetes manifests or Kustomize files. Defines base-and-overlay structure, patch patterns, manifest validation, image-transform limits, and how overlays map to GitOps sync targets.
tier: subject
requires: [plugin:crew@>=0.38.0]
expects-local: [platform-conventions, topology]
---

## Directory structure

Example layout (adapt the root path and environment names to the project — the base/overlay split is the convention):

```
infrastructure/kubernetes/
├── base/<component>/       # Reusable base resources (no env-specific config)
└── overlays/<env>/<app>/   # Environment patches (tolerations, GPU, resources, replicas)
    ├── kustomization.yaml
    └── <patch-files>.yaml
```

Each `overlays/<env>/<app>/` directory is one deployable unit — when the project uses a GitOps controller (Argo CD, Flux, or similar; see its platform-conventions local skill, if it defines one), that directory is the sync target. Base resources are shared — **changes to base manifests propagate to every overlay**. Treat base changes as high blast-radius; prefer overlay patches for environment-specific concerns.

## Control-plane toleration (some clusters)

On clusters that schedule workloads onto control-plane nodes (check the project's platform-conventions local skill, if it defines one), every overlay must include a toleration patch for the control-plane taint:

```yaml
# overlays/<env>/<app>/toleration-patch.yaml
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

On such clusters, pods without this toleration will not schedule anywhere. On clusters with dedicated workers, omit it.

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

GPU overlays additionally require node placement and resource limits — applied via overlay patch, never in base:

```yaml
spec:
  template:
    spec:
      nodeSelector:
        kubernetes.io/hostname: <node-name>   # a GPU node — see the project's topology local skill
      containers:
        - name: <app>
          resources:
            limits:
              nvidia.com/gpu: 1
```

## Manifest validation

Before opening a PR:
```bash
kubectl kustomize infrastructure/kubernetes/overlays/<env>/<app>
```

This validates that the kustomization resolves without error. It does not apply anything to the cluster. Add `kubectl apply --dry-run=server -f -` against a cluster when schema validation against live CRDs matters.

## Static PV shared-asset pattern

To share a read-only asset library (e.g. ML model weights) across namespaces: a dedicated namespace holds static PVs pointing at an NFS (or other RWX) export, and each consumer namespace binds a matching RWX PVC with `storageClassName: ""` to bypass dynamic provisioning.

Do not change `storageClassName` on these PVCs — the empty string is intentional to bind to the static PV. The concrete instance (export host and path, consuming apps, mount wiring) lives in the project's topology local skill, if it defines one.

## Kustomize image transforms

Kustomize image transforms only rewrite fields Kustomize knows are images. They do **not** reach custom resources such as Argo Workflows `WorkflowTemplate`s unless the project teaches Kustomize those field paths (`configurations:`). If pinning an image in such a CRD, set the tag directly in its YAML — do not rely on `images:` in `kustomization.yaml` to propagate there.

## Review checks

When reviewing a change to manifests or Kustomize files (with `k8s-workload-patterns` for the workload spec itself):

- [ ] `kubectl kustomize <overlay>` resolves without error for every overlay the change touches, including overlays that inherit a changed base
- [ ] Environment-specific config (tolerations, GPU, replicas, resources) is patched in an overlay, not written into base
- [ ] A base change is called out as such, with the overlays it reaches
- [ ] On clusters whose platform-conventions local skill requires it, every workload overlay carries the control-plane toleration; on clusters without that rule, none is added
- [ ] GPU workloads: node selector and the GPU resource limit live in an overlay patch, never in base
- [ ] Static-PV PVCs keep `storageClassName: ""`
- [ ] An image pinned inside a custom resource is set in that resource's YAML, not left to `images:`
