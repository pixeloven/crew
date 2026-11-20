---
name: example-co-tracker-fields
description: Example Co's issue-tracker mapping for planning items — a GitHub project, issue types, a field map with how each value is written, and link types. Load before pushing drafts to the tracker or pulling items from it.
---

## Tracker

GitHub Issues in the `example-co/product` repository, with planning fields on the
organisation project "Product planning" (project number 7). Writes go through a
connected tool when available; otherwise a CSV import.

## Issue types

| kind | Issue type | Parent link |
|---|---|---|
| theme | `Bet` | none |
| epic | `Pitch` | sub-issue of a Bet |
| story | `Slice` | sub-issue of a Pitch |
| idea | `Idea` | none |
| discovery | `Pitch` with label `explore` | sub-issue of a Bet |

## Field map

| What we call it | What the tracker calls it | How to write a value | Example |
|---|---|---|---|
| `title` | issue title | plain text, 120 characters at most | Let returning buyers reorder in one step |
| `kind` | issue type | one of the types in the table above | `Pitch` |
| `stage` | project field `Stage` | one option: Inbox, Explore, Shape, Commit, Ship or Learn | `Shape` |
| `theme` | parent Bet | make the item a sub-issue of an existing Bet | sub-issue of #41 |
| `parent` | parent issue | make the item a sub-issue of an existing Pitch or Bet | sub-issue of #58 |
| `size` | project field `Size` | one option: XS, S, M, L or XL | `M` |
| `body` | issue body | Markdown | the draft below its header |

## Link types

`depends-on` and `blocks`: a "Blocked by #N" / "Blocks #N" line in the body. `relates-to`: a plain mention.

## Write policy

The pack may write every field above. Assignees and the project field `Priority`
are always set by a person. Pulled items may be updated in place only after the
diff is shown.
