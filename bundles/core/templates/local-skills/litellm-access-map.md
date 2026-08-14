---
name: <project>-litellm-access-map
description: <Project>'s concrete LiteLLM access map — which surface holds which virtual key, each key's MCP access groups, team ceilings, and where the credentials live. Load before changing any VK scope or granting a surface a new capability. The generic mechanism is the foundation's litellm-routing-model skill.
---

## Surfaces ↔ keys ↔ groups

> **▸ Fill:** a table — surface | VK alias | mcp_access_groups | team. Keep it exhaustive; an undocumented key is an ungoverned one.

## Teams & ceilings

> **▸ Fill:** team names and each team's allowed-groups ceiling.

## Credential locations

> **▸ Fill:** where each key lives (e.g. `op://` paths), and the master-key location for admin operations. Paths only — never values.

## Deployment notes

> **▸ Fill:** the deployed LiteLLM version (fail-open behaviors are version-sensitive — re-verify on upgrade), and any consumer that caches its tool list and needs a roll after VK changes.
