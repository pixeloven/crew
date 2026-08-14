---
name: argocd-deployment-patterns
description: ArgoCD app-of-apps structure — registration (root Application, hand-maintained list vs directory.recurse), sync-wave ordering, the resources-finalizer cascade-delete hazard, health-check semantics, and the base+overlay / one-Application-per-service config-as-code principles. Load when deploying, syncing, registering, or debugging ArgoCD-managed workloads.
tier: subject
requires: [cluster]
audience: [crew]
expects-local: [topology, secret-paths]
---

ArgoCD manages every workload declaratively from git via an **app-of-apps**: one root `Application` registers a set of child `Application`s, one per deployed service. This skill is the generic pattern — a consumer's concrete app inventory, group layout, and wave *numbers* live in that consumer's own local architecture skill, not here.

## Config-as-code principles

Four invariants hold across every consumer:

- **base + overlay.** A Kustomize `base/` holds the environment-neutral manifests; an `overlays/{env}/` layer patches per-environment specifics (tolerations, replicas, node placement). The child Application's `source.path` points at the **overlay**, never at the base. Base changes are high blast-radius — they propagate to every overlay that references them.
- **One Application per service.** Each deployed service is exactly one child Application. Don't bundle unrelated services into a single Application (blast radius, unclear ownership) or split one service across several (partial-sync hazards).
- **Explicit `destination.namespace`.** Every Application sets its target namespace explicitly — never rely on inference. An inferred namespace is silent drift waiting to happen.
- **Never `kubectl apply` in production.** Change git; let ArgoCD sync. Direct applies create drift ArgoCD will either fight (selfHeal) or mask.

## Registration — how a child Application is discovered

The root Application has to *find* each child. Two mechanisms:

| Mechanism | How | Failure mode |
|---|---|---|
| **Hand-maintained list** | root `source.path` is a kustomize dir whose `kustomization.yaml` names each child file under `resources:` (recurse off) | **Silent drop** — add a new app file but forget the list entry and it is *never registered*, with no error. |
| **`directory.recurse: true`** | root uses a `directory` source that auto-discovers every manifest under a path tree | New file in the tree → auto-registered. No list to forget. |

**Recommend `directory.recurse: true`** — it removes the "forgot the list entry" landmine entirely. With the hand-list, adding a child is a two-step edit (the manifest *and* the `resources:` entry), and the second step fails silently; the recurse source makes registration a property of *where the file lives*.

## The cascade-delete hazard (governs every topology change)

Each child Application typically carries the `resources-finalizer.argocd.argoproj.io` finalizer. That finalizer means: **when a child Application leaves the generated set, ArgoCD prune-deletes its live workloads — and, for a stateful service, its PVCs.** Three edits all trigger it:

- **Removing** a child Application from the set (deleting its file, or dropping its `resources:` entry).
- **Renaming** its `metadata.name` — ArgoCD sees the old name disappear and the new one appear: prune old (delete workloads) + create new.
- A **re-rendering `source.path`** change — repointing an Application at a path that renders differently is a prune+recreate of whatever changed.

> **Safety invariant** — a topology change is safe **iff all three hold**:
> 1. `argocd app diff <app>` is **empty**, **and**
> 2. `argocd app get root` (i.e. the generated child set) shows **no Application added or removed**, **and**
> 3. `diff <(kustomize build OLD) <(kustomize build NEW)` is **byte-identical**.
>
> A change that fails any of the three is a delete/recreate — do it as a create-new (`prune: false`) → verify → remove-old cutover, migrating any PVC data first.

Moving an Application manifest *file* within a recurse tree, or setting a placement-neutral field, is safe: name / path / destination unchanged clears the invariant trivially.

## Sync waves

ArgoCD sync waves order resource creation within a sync; lower numbers apply first, and ArgoCD waits for each wave to be healthy before starting the next. The **generic ordering principle**:

> **infrastructure / CRDs → dependents → workloads → cleanup**

That is: things others depend on (namespaces, CRDs, StorageClasses, operators, shared secrets) come before the things that need them; leaf application workloads come after their dependencies; anything that must run *last* (cross-namespace reapers, cleanup jobs) sits at the highest wave.

The specific wave *numbers*, and which app sits in which wave, are a **consumer's own** — read them from the live `argocd.argoproj.io/sync-wave` annotations and document them in that consumer's local architecture skill. Do **not** assume a fixed taxonomy (e.g. "wave 1 = namespaces, wave 2 = databases, wave 3 = workloads"): real deployments split waves in ways only the annotations reveal (a dependency and its addon can legitimately land in different waves).

Set a wave with an annotation on the resource or Application:
```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"
```

## Sync operations

**Read paths** route through the platform's federated ArgoCD MCP tools — the LiteLLM virtual key in the MCP client config authenticates, so individual calls need no extra credentials:
```
argocd-list_applications                # all apps with health/sync status
argocd-get_application                  # one app's sync + health + resources
argocd-get_application_workload_logs    # recent pod logs for an app's workloads
```

**Health sweep pattern** (Investigator): `list_applications` → identify Degraded / OutOfSync apps → `get_application` for resource-level status → `workload_logs` for error detail → cross-reference `kubectl` for node-level or persistent-volume issues.

**Do not assume the MCP surface is read-only.** The upstream ArgoCD MCP server also carries write tools (`argocd-sync_application`, create/update/delete application, `run_resource_action`), and a VK granted the server sees them unless they are scoped out. The platform **convention** is that agents treat MCP ArgoCD as read-only — automated syncs go through ArgoCD's GitOps reconciler, and manual syncs use the CLI with human intent. Enforce the convention structurally with a per-server `allowed_tools` allowlist on the VK's access path (see `litellm-routing-model`), not by trusting agents to abstain.

**Write operations** (sync, rollback) use the CLI:
```bash
export ARGOCD_SERVER=<argocd-host>                                    # your platform's endpoint (topology skill)
export ARGOCD_AUTH_TOKEN=$(op read "op://<vault>/ArgoCD/agent_token") # concrete op:// path in the secret skill

argocd app sync <app-name>
argocd app wait <app-name> --health --timeout 300
```

**Fallback** (no CLI, no MCP):
```bash
kubectl get applications.argoproj.io -n argocd
```

## Health check semantics

ArgoCD derives app health from Kubernetes resource health. Common states:
- **Healthy** — all resources in their expected state.
- **Progressing** — resources updating (pods starting, rollout in progress).
- **Degraded** — one or more resources failed or errored.
- **Missing** — an expected resource is absent from the cluster.
- **Suspended** — a resource is paused (e.g. a suspended CronJob).

**OutOfSync** (orthogonal to health) means live state diverges from git — expected mid-deploy, resolves once sync completes. A *persistently* OutOfSync app whose `app diff` is empty usually means a mutating admission controller or a defaulted field; investigate rather than force-sync.

## Debugging a degraded app

```bash
argocd app get <app-name>                  # overview: sync + health
argocd app get <app-name> -o json          # full detail incl. resource conditions
kubectl get pods -n <namespace>            # pod state
kubectl describe pod -n <namespace> <pod>  # events and conditions
kubectl logs -n <namespace> <pod>          # container logs
```

For ExternalSecret failures specifically, see `secret-management-patterns`.

## Adding a new service

1. Author the `base/` manifests and an `overlays/{env}/` patch (see `k8s-kustomize-conventions`).
2. Add a child Application whose `source.path` is the overlay and whose `destination.namespace` is explicit.
3. Register it: with `directory.recurse` the file's location *is* the registration; with a hand-list, add the `resources:` entry too — or the app is silently dropped.
4. If you touched any existing Application's `metadata.name` or `source.path`, clear the cascade-delete safety invariant before merge.

GPU or placement-specific workloads add a node-selector / affinity / toleration patch in the overlay — see the platform conventions skill.
