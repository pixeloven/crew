# Infrastructure seam seed entries

Starter entries for a project's **existing** `protected-seams` registry (Crew's
stub at `templates/local-skills/protected-seams.md`), one per shape, written in
that stub's terms: the **protected pattern** to scan a diff for, the **risk** if
it changes silently, and the **response**. Copy the ones that apply, rewrite each
pattern and grep for the project's real resources and paths, and commit them
through the registry's approval rule. These are shapes, not facts: the invariant
values come from the project's `platform-conventions`, and the store name from
its `secret-paths`.

The **response** — urgency and who signs off — is deliberately left blank. That
is the project's call, recorded once in its registry; this pack does not make it.

No entry may hold a secret or a credential reference.

Every grep reads the change against its merge base. Set `BASE` to the target
branch (`BASE=origin/main`), and keep only added or changed lines when a grep
matches too much.

---

## Secret-sync contract

- **Protected pattern:** secret-sync custom resources and their refresh interval,
  deletion or reclaim policy, and store reference; the store objects themselves;
  any literal secret, token, password or API key in a changed file; a sync object
  added with no consumer workload in the same change. With External Secrets
  Operator these are `ExternalSecret`, `SecretStore` and `ClusterSecretStore`,
  with `refreshInterval`, `deletionPolicy` and `secretStoreRef`; Sealed Secrets
  and a CSI secrets-store driver have their own equivalents.
- **Risk:** a secret that re-syncs when the project expects it fixed, follows its
  sync object into deletion, or comes from an unregistered store breaks the
  workloads reading it, or hands a credential to a store nobody reviews.
- **Response:** `<urgency and reviewers — set by the project>`

```bash
git diff "$BASE"...HEAD -- '*.yaml' '*.yml' \
  | grep -E '^\+.*(kind: (Cluster)?SecretStore|kind: ExternalSecret|kind: SealedSecret|kind: SecretProviderClass|refreshInterval|deletionPolicy|secretStoreRef)'
gitleaks detect --source . --no-git   # literal secrets, any file type
```

## Scheduling and storage tier

- **Protected pattern:** workloads (`Deployment`, `StatefulSet`, `DaemonSet`,
  `Job`, `CronJob`) whose `tolerations`, `nodeSelector` or affinity drop what the
  project requires; `storageClassName` on a PVC or volume claim template moved
  between the project's tiers or to an unlisted class; `storageClassName: ""`
  outside a documented static-PV binding.
- **Risk:** a workload without the required toleration never schedules; one with
  a stray selector lands on the wrong hardware. Data on the wrong tier is lost
  when a `Delete`-reclaim volume goes, or kept forever on a `Retain` one.
- **Response:** `<urgency and reviewers — set by the project>`

```bash
git diff "$BASE"...HEAD -- '*.yaml' '*.yml' \
  | grep -E '^[-+].*(storageClassName|tolerations|nodeSelector|affinity|node-role)'
# Then confirm every changed workload still carries what platform-conventions requires:
kubectl kustomize <overlay> | grep -E '^kind: |tolerations:|storageClassName:'
```

## Authorization widening

- **Protected pattern:** new `Role`, `ClusterRole`, `RoleBinding` or
  `ClusterRoleBinding` manifests; new `subjects:` on an existing binding; verbs
  added to existing `rules:` (above all `delete`, `deletecollection`, `patch`,
  `update` where only `get`, `list`, `watch` were); `*` in `verbs`, `resources`
  or `apiGroups`; `escalate` or `bind` on roles, `create` on bindings,
  `impersonate` on users, groups or service accounts; a broad group subject; a
  `ClusterRole` where a namespaced `Role` would do.
- **Risk:** authorization widens with no code change. A report-only identity
  becomes one that deletes, or a single namespace's grant reaches the cluster.
- **Response:** `<urgency and reviewers — set by the project>`

```bash
git diff "$BASE"...HEAD -- '*.yaml' '*.yml' \
  | grep -E "(kind: (Cluster)?Role(Binding)?|^\+.*(verbs|resources|apiGroups|subjects):|^\+.*\*|^\+\s*-\s*[\"']?[a-z0-9./-]*[\"']?\s*(#.*)?$)"
git diff "$BASE"...HEAD | grep -E '^\+.*(escalate|bind|impersonate|deletecollection|system:authenticated|system:serviceaccounts)'
```

## LLM or tool-gateway access

- **Protected pattern:** the gateway's access configuration — which tool servers
  are registered, which access groups each belongs to, each team's allowlist of
  groups, each key's grants, and each server's tool allowlist. The load-bearing
  boundary is the intersection of the three grants (server groups ∩ team
  allowlist ∩ key grants), not a split between credential types.
- **Risk:** a consumer reaches a model or tool it was never granted. Gateways
  often fail open: a group that matches no server, or a key with no groups, may
  be read as "unrestricted" rather than "nothing".
- **Response:** `<urgency and reviewers — set by the project>`

Worked example, LiteLLM: server `access_groups` in the proxy config's
`mcp_servers` block, team and key `object_permission.mcp_access_groups`, and
per-server `allowed_tools`. Rewrite the grep for the project's gateway.

```bash
git diff "$BASE"...HEAD \
  | grep -E '^[-+].*(mcp_servers|access_groups|mcp_access_groups|object_permission|allowed_tools)'
```
