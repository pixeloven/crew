---
name: <project>-platform-conventions
description: <Project>'s deployment conventions — scheduling tolerations, StorageClass tiers, pod security context, secret patterns, and namespace policies. Load when authoring or reviewing any workload manifest. Name the silent landmines imperatively here (they make the skill load when it matters).
---

## Scheduling

> **▸ Fill:** required tolerations / node selectors and *why* (e.g. "all nodes are control-plane — a workload without the control-plane toleration stays Pending forever").

## Storage tiers

> **▸ Fill:** your StorageClass names, what each is for (runtime/ephemeral vs retained data), and each tier's reclaim policy.

## Pod security

> **▸ Fill:** the standard securityContext block (runAsNonRoot, seccompProfile, fsGroup value, dropped capabilities) and any namespace that legitimately runs at an elevated PodSecurity level.

## Secrets

> **▸ Fill:** the secret flow (e.g. 1Password → ESO), the registered ClusterSecretStore name, and the ExternalSecret invariants that must never change silently.

## Namespaces & misc

> **▸ Fill:** namespace layout conventions, ingress/domain patterns, GPU workload placement, anything a manifest author must not guess.
