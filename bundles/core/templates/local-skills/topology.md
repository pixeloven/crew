---
name: <project>-topology
description: <Project>'s cluster topology — nodes, IPs, roles, service domains, DNS model, and expected state. Load when diagnosing cluster issues, writing workloads, or reasoning about network paths.
---

## Nodes

> **▸ Fill:** node inventory table — name, IP(s), role, special hardware (GPU), and any hypervisor/host mapping.

## Service domains & DNS

> **▸ Fill:** the domain scheme, where DNS is managed, internal vs external resolution.

## Access paths

> **▸ Fill:** how agents reach the cluster (kubeconfig source, API endpoints, CLI contexts) — read-only vs admin paths.

## Expected state

> **▸ Fill:** what "healthy" looks like — the workloads that must always be running, and known-acceptable oddities that should not be reported as findings.
