---
name: infra-seams
description: Use when a diff touches secret-sync objects, tolerations, storage classes, RBAC, or an LLM/tool gateway's access config. Detects infrastructure seam crossings, states the authority delta, seeds the seams registry.
tier: concept
requires: [plugin:crew@>=0.38.0]
expects-local: [protected-seams, platform-conventions, secret-paths]
---

# Infrastructure seams

Crew's `seam-detection` defines what a seam crossing is and how to report one;
`seam-alert-routing` defines who signs off. This skill adds the **infrastructure
shapes** to detect. Where the project has a `protected-seams` local skill, its
entries are the record of truth — names, urgency and reviewers — and outrank
everything below. `platform-conventions` holds the invariant values a shape is
checked against (the toleration, the storage tiers, the secret-sync settings);
`secret-paths` names the one secret store the project registers.

This skill never fills `protected-seams`. A project keeps one registry for every
kind of seam, with an approver behind it. With no registry, detect by the shapes
below, say the registry is missing, and offer the seed entries.

## Four shapes

| Shape | What it protects | Where it hides |
|---|---|---|
| **Secret-sync contract** | secrets arrive once, from the registered store, and outlive their sync object | secret-sync custom resources (an External Secrets `ExternalSecret`, a `SealedSecret`, a CSI driver `SecretProviderClass`); their refresh interval, deletion or reclaim policy, store reference; literal secrets anywhere in the diff |
| **Scheduling and storage tier** | workloads land where they can run, and data lands on the tier whose reclaim policy matches it | `tolerations`, `nodeSelector`, affinity; `storageClassName` on PVCs and volume claim templates; static-PV bindings with `storageClassName: ""` |
| **Authorization widening** | each identity can do only what it does today | `Role`, `ClusterRole` and their bindings; `verbs`, `resources`, `apiGroups`, `subjects`; wildcards; escalation-adjacent verbs |
| **LLM or tool-gateway access** | each consumer reaches only the models and tools it was granted | the gateway's per-server access groups, per-team allowlists, per-key grants, and per-server tool allowlists; new servers or tools registered with the gateway |

The project's registry may split, merge, rename or drop these. A shape is a place
to look; what makes a crossing is what the change lets something do.

## Method

1. **Scope the diff.** List changed files. Mark manifests, Helm values, Kustomize
   overlays, gateway config, and anything under the paths the registry names.
2. **Match the registry first.** Test each registry entry's patterns. A hit is
   reported under the entry's own name, with its urgency and reviewers.
3. **Then test the four shapes** against what the registry missed, using the
   greps in [the seed file](seed-seams.md). Compare each value with the
   project's `platform-conventions` invariant rather than with a number in this
   skill: if the project says secrets sync once, a non-zero refresh interval is
   the crossing; if it says nothing, ask.
4. **State the delta in authority.** For each crossing: what this identity,
   workload or consumer could do or reach before, what it can after, and the
   worst outcome the new path allows. For RBAC, name the new verb on the named
   resource; for a gateway, name the tool or model newly reachable and by whom.
5. **Report** in `seam-detection`'s finding format and route through
   `seam-alert-routing`. Reviewers come from the matched registry entry. For a
   crossing no entry covers there is no default reviewer: say which shape it
   crosses and ask the operator who reviews it here.
6. **Propose registry entries.** For a crossing the registry did not name, draft
   an entry from [the seed file](seed-seams.md) for the operator, with urgency
   and reviewers left for them to set. Do not write it into the registry yourself.

## Diff shapes that are always Required

- a literal secret, token, password or key in any changed file;
- a secret-sync object pointed at a store other than the one `secret-paths`
  registers, or its deletion policy changed so that deleting the object deletes
  the secret;
- a secret-sync object with no consumer workload in the same change;
- a workload missing a toleration or node selector the project's
  `platform-conventions` says every workload needs;
- a `storageClassName` moved between tiers, or to a class the project does not
  list;
- an RBAC rule gaining `delete`, `deletecollection`, `patch`, `update`,
  `escalate`, `bind` or `impersonate`, a `*` wildcard, or a broad group subject
  (`system:authenticated`, `system:serviceaccounts`);
- a namespaced `Role` replaced by a `ClusterRole`;
- a gateway allowlist widened or removed, or a group or key left matching
  nothing, where the gateway treats an empty grant as unrestricted.

The RBAC case shows why the delta matters more than the diff size: an auditor
that only reports, because its role grants only `get` and `list`, becomes a
reaper when `delete` is added to that list. No code changes.

## Not a crossing

- a label or annotation added to a secret-sync object without touching its
  refresh, deletion or store fields;
- a new `Role` that only adds `get` or `list` on resources the identity could
  already read (a Note, not Required);
- a resource request or limit change with no scheduling or storage field touched;
- a gateway config change to logging, timeouts or model aliases that grants no
  new reach.

When unsure, flag. A false positive costs a short discussion; a missed crossing
can take down a cluster or hand out a credential.

## Onboarding: seed the registry

During Crew onboarding, or when asked, open [seed-seams.md](seed-seams.md) and
propose the entries that apply to this project for its existing `protected-seams`
registry, each pattern rewritten for the resources and paths you found. Each
proposed entry is a diff the operator commits, and it needs the registry's
approver. If the project has no registry, propose creating it from Crew's
`protected-seams` stub with these entries, as one choice for the operator.

## Depth

| Mode | When | Output |
|---|---|---|
| Quick | a small diff, one shape plausible | findings list, shapes checked |
| Thorough | an RBAC, secret-sync or gateway change; or no registry | findings, authority delta per crossing, proposed registry entries |
| Critique | an existing seam review or registry | gaps, false positives, shapes with no entry or no reviewer |
