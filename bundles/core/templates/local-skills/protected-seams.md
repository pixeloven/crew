---
name: <project>-protected-seams
description: Registry of <Project>'s load-bearing patterns that require human sign-off when a diff touches them. Load when reviewing or authoring changes near secrets, scheduling, access boundaries, or runtime contracts. The foundation's seam-detection / seam-alert-routing skills check against this registry.
---

Seams are named, narrow, and machine-detectable. For each seam record: the protected
pattern (what to scan for in a diff), the risk (what breaks if it changes silently), and
the response (flag, don't block).

## Seams

> **▸ Fill:** one section per seam. Common shapes worth considering: a secret-management
> contract (refresh/deletion invariants), a scheduling contract (tolerations, storage
> tiers), an access boundary (who can reach which tools), a runtime contract (exit codes,
> result formats). Your registry may have more, fewer, or different entries.

## Registry ownership

> **▸ Fill:** who approves seam crossings, and how new registry entries are added (typically: PR + owner approval).
