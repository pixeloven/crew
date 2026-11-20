---
name: tracker-sync
description: Use only when asked to push planning drafts to an issue tracker or pull tracker items into drafts. Maps fields through the project's tracker-fields slot, shows every field before writing, never invents IDs; with no tracker connection, writes an import file.
tier: subject
requires: [plugin:crew@>=0.45.0]
expects-local: [tracker-fields]
---

# Tracker sync

Move this pack's Markdown drafts into an issue tracker, and tracker items back into
drafts the other skills can score. It runs **only when the operator asks**; no other
skill in this pack writes to a tracker. Where the project has a `tracker-fields`
local skill, it is the only source of tracker identifiers this skill uses.

A connected tracker (the `mcp:tracker` capability, bound by the project's capability
map to whichever tracker it uses) is optional. Without one, this skill writes an
import file or paste-ready text instead, and the operator does the last step.

## The draft header

Every draft from this pack starts with a header keyed by **logical** field names:

```yaml
---
kind: idea | theme | epic | story | discovery
title: ...
stage: ...
theme: ...
parent: ...
size: ...
tracker-key:      # empty until synced; then the tracker's key for this item
---
```

The body below the header is the item's description. Logical names never change
from tracker to tracker; the slot's **Field map** translates them.

## Depth modes

| Mode | Use when | Output |
|---|---|---|
| **Quick** | first sync, or checking a mapping | a dry run: every item, field and link that would be written, nothing sent |
| **Thorough** | the operator approves the dry run | the write (or the import file), then each draft's `tracker-key:` updated |
| **Critique** | drafts and tracker may have drifted | a field-by-field diff between each synced draft and its tracker item |

Default to Quick on a first sync for a project; the operator can go straight to
Thorough.

## Push

1. **Resolve the map.** Read the field map in the `tracker-fields` slot. For each
   field in the drafts, find what the tracker calls it and how a value must be
   written. A field with no row, or a value the row does not allow, is
   **unresolved**.
2. **Unresolved means stop**, for that field. Do not guess an identifier from a
   display name, an earlier session, or another project. Tell the operator which
   fields are unresolved, and either (a) leave them out of this sync with their
   agreement, or (b) fill the slot first — crew's `learn` can draft the missing
   `tracker-fields` sections from the connected tracker's own metadata as a proposal
   they promote.
3. **Show every write.** List, per item: create or update, every field and value,
   every link (`depends-on`, `blocks`, parent). This is crew's confirm-before-write
   rule; wait for the operator.
4. **Write.** Items with a `tracker-key:` are **updated**, never re-created, so re-runs
   do not duplicate. New items are created parents first, so children can link.
5. **Record.** Put each new key into its draft's `tracker-key:` line and report
   what was written, what was skipped, and why.

## Without a tracker connection

Produce the same content as a file the operator imports or pastes:

- **Import file** (CSV, or JSON where the tracker imports it) — one row per item,
  columns named by what the tracker calls each field. With no slot, use the pack's
  own field names as columns and tell the operator to map them in the tracker's import screen.
- **Paste-ready text** — per item, the title and the body formatted for the
  tracker's description field, with field values listed above it.

Write the file next to the drafts (e.g. `planning/drafts/import-<date>.csv`) and ask
the operator to paste back the keys once imported, so `tracker-key:` lines can be
filled and the next run updates instead of duplicating.

## Pull

Read the items the operator names (or a query they give) from the connected
tracker — or, with no connection, from an export or paste they provide — and write one draft per
item with the header filled from the slot's map in reverse and the description as
the body. Fields with no reverse mapping go in a `**Tracker fields not mapped:**`
line, not into the header. Pulled drafts are inputs for
[`readiness-gates`](../readiness-gates/SKILL.md) and the other skills; pulling never
changes the tracker.

## With no slot filled

Pushing through a connected tool needs identifiers, so it cannot proceed: say so,
offer the import-file path, and suggest running crew's `learn` against the tracker
to draft the `tracker-fields` slot. Pull and the import-file path both work without
the slot, using the pack's own field names.
