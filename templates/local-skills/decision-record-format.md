---
name: <project>-decision-record-format
description: <Project>'s house format for decision records (ADRs) — where they live, how they are numbered and named, the template and status values. Load when writing, reviewing or superseding a decision record. Crew's decision-records skill defers its format to it.
---

Crew's `decision-records` skill owns the practice: when to write a record, its
required content, and how superseding works. This skill holds only what is
specific to this project.

## Location and naming

> **▸ Fill:** where records live (a repo directory such as `docs/decisions/`, or a
> knowledge-corpus path), how they are numbered or named, and any index or README
> that must be updated alongside a new record.

## Template

> **▸ Fill:** the record template, or a pointer to the template file the project
> already keeps (e.g. `docs/decisions/_template.md`). Keep the section names your
> records actually use.

## Status values

> **▸ Fill:** the statuses a record moves through (e.g. proposed → accepted →
> superseded) and how a superseded record links to its replacement.

## Approval

> **▸ Fill:** who accepts a record, and how (e.g. PR review by the owning team).
