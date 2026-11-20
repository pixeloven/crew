---
name: <project>-tracker-fields
description: <Project>'s issue-tracker mapping for planning items — tracker kind, project identifiers, issue types, a field map saying how each value is written, and link types. Load before pushing planning drafts to the tracker or pulling items from it.
---

<!-- planning-skills slot: tracker-fields. Read by tracker-sync.
     Most of this is discoverable: with a tracker connected, crew's `learn` can draft these
     sections from the tracker's own metadata as a proposal for the operator to promote.
     tracker-sync never guesses an identifier; an unresolved field stops the sync. -->

## Tracker

<!-- crew:discoverable capability=mcp:tracker -->

> **▸ Fill:** the tracker product, the project / space / board identifiers planning items live in, and whether writes go through a connected tool or an import file (CSV, JSON) the operator uploads.

## Issue types

<!-- crew:discoverable capability=mcp:tracker -->

> **▸ Fill:** the tracker's issue type for each planning `kind` (idea, theme, epic, story, discovery), and how parent–child is expressed (a parent field, a sub-issue relation, a link).

## Field map

<!-- crew:discoverable capability=mcp:tracker -->

> **▸ Fill:** one row per field the pack's drafts carry. Trackers often show one name on screen and expect another through their API or import; write the one a write must use, and put the on-screen name in brackets after it if the two differ.

| What we call it | What the tracker calls it | How to write a value | Example |
|---|---|---|---|
| `title` | ▸ | ▸ | ▸ |
| `kind` | ▸ | ▸ | ▸ |
| `stage` | ▸ | ▸ | ▸ |
| `theme` | ▸ | ▸ | ▸ |
| `parent` | ▸ | ▸ | ▸ |
| `size` | ▸ | ▸ | ▸ |
| `body` | ▸ | ▸ | ▸ |

## Link types

<!-- crew:discoverable capability=mcp:tracker -->

> **▸ Fill:** the link types used for `depends-on`, `blocks` and `relates-to`, by their exact names in the tracker.

## Write policy

> **▸ Fill:** which fields the pack may write, which a human always sets (e.g. owner, priority), and whether pulled items may be updated in place or only drafted locally.
