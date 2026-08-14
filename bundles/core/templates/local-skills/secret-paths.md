---
name: <project>-secret-paths
description: <Project>'s concrete secret locations — vault names, item/field paths, store names, and which workload consumes which secret. Load when creating or rotating credentials, or wiring an ExternalSecret. The generic flow is the foundation's secret-management-patterns skill.
---

## Stores

> **▸ Fill:** the registered secret store(s) (e.g. the ClusterSecretStore name) and the backing vault/account.

## Credential inventory

> **▸ Fill:** a table — credential | path (e.g. `op://<vault>/<item>/<field>`) | consumed by | rotation notes. Paths only — never values.
