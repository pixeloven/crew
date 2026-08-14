---
name: vault-curation-patterns
description: Decision framework for the librarian agent — how to resolve each lint finding type, when to MOC vs tag, when to archive vs invalidate, how to recognize Dataview-covered notes. Load when triaging lint findings or running a curation pass.
tier: concept
requires: [mcp:kb]
audience: [crew]
expects-local: [vault-ops]
---

The traditional `daily_lint` runner is the *ingredient list*. This skill is the *recipe* — how the `librarian` agent (or an operator running curation manually) decides what to actually do for each finding. The goal is **zero standing findings**, not by suppression but by resolution.

Core scope is **quality** (orphans, broken links, schema gaps). Enhancement, aging, and consolidation are adjacent concerns — see *Out of scope* below.

## Inputs

- Latest `daily_lint` review note (kind=review, tag=lint, in `notes/`)
- Vault content + lifecycle metadata via the `vault.*` MCP surface — see `vault-tools` skill
- Vault content conventions (kind enum, type enum, tag taxonomy) — see `vault-tools`, plus the corpus's own conventions note if the deployment keeps one

## Triage rules (apply across all finding codes)

Three meta-rules that hold across the per-code decision tables. They came out of early supervised curation passes; they're folded in here so no pass has to re-learn them.

### Rule 1 — Tool-bug findings defer to a code fix, never patch content

When a finding is caused by a **parser limitation, sync bug, or scanner gap** (not by actual content drift), the right call is to ship a code fix and defer the finding. **Do not rewrite valid content to dodge the bug.**

Example: a large batch of `broken_link` findings turn out to be syntactically correct `[[stem|alias]]` wikilinks pointing at existing files — the parser captured `stem|alias` verbatim and the resolver couldn't match it. Right call: ship the one-line parser fix. Wrong call: strip pipe aliases from dozens of source notes.

How to recognise: if "fix" means "rewrite content that's actually correct by the convention," it's a tool bug. Defer to a code fix PR.

### Rule 2 — Walk broken_link before orphan in each pass

Resolving broken links can change which notes appear as orphans. A note that's covered by a broken-link-but-soon-to-be-resolved wikilink shouldn't get marked `orphan_ok: true` — once the link resolves, it has incoming connectivity and doesn't need the suppression flag.

Severity ordering already enforces this when followed strictly (HIGH → MED → LOW), since `broken_link` is HIGH and `orphan` is LOW. The rule exists so the agent doesn't shortcut the ordering when one severity feels easier than another.

### Rule 3 — Don't depend on un-deployed code in autonomous edits

When the agent applies an autonomous edit, the edit must be **immediately valid** under the currently-deployed scanner — not "valid once PR #X lands." If the only way to make the edit valid is a code change still in review, the right path is to either:

- Use a form that's valid under the current scanner (e.g. plain `[[full-stem]]` instead of `[[full-stem|alias]]` when alias-stripping hasn't deployed), or
- Defer the edit to a follow-up pass that runs after the code change deploys.

Example: rewriting a topic cluster's wikilinks to `[[full-stem|short-slug]]` (alias form) while relying on a pipe-strip fix not yet deployed makes the next lint show `broken_link` going UP instead of down. The recovery: re-do as `[[full-stem]]` (no alias) so resolution is immediate; a future pass can re-add aliases for readability after the fix deploys.

## Per-finding decision framework

### `broken_link`

The finding tells you a `target_id` that has no matching note. Read the source note around the wikilink to understand intent:

| Condition | Action |
|-----------|--------|
| Target was archived or superseded | Strip the wikilink; replace with plain text of the alias (if `[[stem\|alias]]`) or stem |
| Target exists under a different name | Rewrite the wikilink to the correct stem; verify by stem search |
| Target *should* exist (operator clearly meant to write it later) and is high-value | Write a thin stub note (`kind: note`, tags matching the cluster) and leave the wikilink; otherwise convert to plain text |
| Target was a Dataview-aggregated reference written as a wikilink by mistake | Replace the wikilink with the corresponding Dataview query block |

Default: when in doubt, **convert to plain text**. Forward references that may never materialize accumulate noise.

### `orphan`

The finding tells you a note has no incoming or outgoing links. Recognize **intentional orphans** before acting:

| Signal | Decision |
|--------|----------|
| Note is referenced by a Dataview query (frontmatter matches a query's `WHERE` clause anywhere in the vault) | Not really an orphan. Add `orphan_ok: true` to its frontmatter so subsequent lints skip it. (Alternative: extend the lint to read Dataview blocks — see open questions.) |
| Note is a credential reference, runbook, or other single-purpose standalone the operator clearly intended | Add `orphan_ok: true` to frontmatter |
| Note is part of a topic cluster with peers (3+ notes share a tag) | Author or extend the cluster's MOC. The MOC body uses a Dataview query (`LIST FROM "notes" WHERE contains(tags, "<topic>")`) to aggregate. Tag the orphan to match. |
| Note is obsolete (superseded by newer content) | Move to `archive/` and run `vault_invalidate(note_id, reason)` |
| Note is one-off and not worth a MOC | Add `orphan_ok: true` with a brief justification in the frontmatter |

Default: **prefer tag + Dataview MOC** over hand-rolling a wikilink list. MOCs become thin (`one or two paragraphs of prose + Dataview queries`); the tag does the connecting.

### `missing_kind`

Pick the right kind by reading the note:
- Reference text, runbook, decision, etc. → use the matching `kind:` value (see kind enum)
- Legacy note (predates the kind schema) that's mostly prose → `kind: note`

### `missing_recommendation` (for `kind: research`)

Either:
- Add a `recommendation:` frontmatter field summarizing the note's conclusion (one sentence)
- Or downgrade to `kind: note` if the note isn't really option-analysis-shaped — in practice the downgrade clears most of these findings

### `deprecated_field`

For vault-wide cleanup, run the deployment's frontmatter-backfill job if it ships one (name in the project's vault-ops local skill). Per-note: rename `author → source_agent`, `created → created_at` (with ISO-8601 +tz), drop `id`/`migrated_at`/`migrated_from`.

### `tag_artefact`

Numeric or 6-char hex tags from Obsidian's inline-tag scanner. Remove from frontmatter; if the artefact was inside body text (`#42` GitHub issue ref), wrap in backticks or rephrase.

## MOC patterns (thin vs rich)

MOCs are fluid. Two common shapes:

**Thin / topic-aggregator** — when a tag cluster is the membership criterion. Body is a few paragraphs + Dataview query:
```
` ` `dataview
LIST FROM "notes" WHERE contains(tags, "substrate")
SORT file.name ASC
` ` `
```

**Rich / project-spanning** — when cross-topic curation has prose value. Hand-picked wikilinks for specific callouts + Dataview queries for the bulk. Example: a project MOC linking architecture decisions and pulling in active research via a query.

Either way, **tag the member notes first** — the leverage point is the frontmatter, not the MOC body.

## Recognizing Dataview-covered notes (semantic non-orphans)

Traditional lint treats a note as orphan iff it has zero links in the `links` table. Dataview queries (rendered at view time) never appear there. To avoid false positives:

- **Read Dataview blocks** in all `kind: note, type: moc` notes
- **Match the query's `WHERE` clause** against the candidate orphan's frontmatter (tag membership, kind, path prefix)
- If matched → not an orphan; optionally set `orphan_ok: true` for the next mechanical lint

This is the canonical "semantic check" the agent does that traditional lint can't.

## Autonomous vs deferred

The curator can act **autonomously** on single-note non-destructive resolutions:

- Frontmatter edits on a single note (`kind`, `source_agent`, `orphan_ok`, tag additions for cluster membership)
- Wikilink rewrites *within a single source note* (strip broken target, swap stem to correct name, replace with plain text)
- Adding a note to an *existing* MOC's tag-membership (when the MOC uses a Dataview query, "adding" means tagging the note; when it uses manual wikilinks, "adding" means editing the MOC body)

Everything else **defers to the session note as an action item** for operator approval:

- Creating a new MOC (even when a cluster is obvious)
- Moving a note to `archive/`
- Multi-note wikilink campaigns (rewriting the same broken target across many sources)
- `vault_invalidate` (irreversible per the substrate spec)
- Anything where the right action requires the operator's judgment call

Bias toward deferring when uncertain. The session note's `Action items` section is cheap to read; an unwanted autonomous action is expensive to undo.

## Workflow

1. **Pre-Task Recall** — `vault_search(query="vault curation preferences", mode="semantic")`. Surfaces any operator-correction patterns from prior sessions (librarian writes them as `kind: fleeting` notes tagged `curation`).
2. **Read** the latest `daily_lint` review note (`vault_findByTag(tag="lint")`, take most recent by date). Skim the totals and per-code breakdown.
3. **Triage** findings by severity (HIGH → MED → LOW), then by code. Within each code, work the table in this skill.
   - HIGH: `broken_link`, `missing_kind`, `unparseable_frontmatter`
   - MED: `tag_artefact`, `deprecated_field`, `missing_recommendation`
   - LOW: `orphan`, `stale`
   - **Always finish `broken_link` before starting `orphan`** (Triage Rule 2). A note covered by a soon-to-be-resolved wikilink should not be stamped `orphan_ok` just because the link is currently broken.
4. **Act** autonomously per the *Autonomous vs deferred* rules. Use `vault_editNote` / `vault_updateFrontmatter` / `vault_addTags` for content and metadata edits; never `vault_deleteNote` autonomously (deletion is deferred).
5. **Document** every decision (acted-on or deferred) in the session note. Per-finding format:
   ```
   ### [SEV] code — subject
   - Decision: <action taken | deferred>
   - Reasoning: <why>
   ```
6. **Re-run** the lint as a one-shot Job from the deployment's lint CronJob (`kubectl create job --from=cronjob/<lint-cronjob>` — name in the project's vault-ops local skill). Verify the count moved as expected; note any surprises in the session note's Recommendation block.
7. **Post-Session Persistence** — `vault_extractFleetingFromTranscript(messages=<session>, source_agent="librarian")`. Captures any new operator-correction patterns or learned preferences as fleeting notes for the next pass.

The session note IS the audit trail. Operator review of the session note is the gate before any deferred action items get executed.

## Out of scope (for this framework)

- **Enhancement**: identifying notes that should be elevated to runbooks, decisions, or architecture
- **Aging**: applying the `valid_until` / supersession flow to notes that have lost relevance
- **Consolidation**: merging duplicate or fragmented notes

Each of these deserves its own pattern section when a deployment takes it on; keep the quality loop settled first.

## Settled design decisions

- **Dataview-coverage detection lives in the curator, not the lint.** `daily_lint` stays mechanical and cheap. The curator reads MOC bodies, parses Dataview blocks, evaluates query coverage against orphan candidates, and stamps `orphan_ok: true` (with reasoning) on any note covered by a Dataview query.
- **Session notes land flat in `notes/` with `tag: curation`.** Discoverable via `vault_findByTag(tag="curation")`, consistent with the daily-lint review-note convention.
- **Operator-approval gate**: see the *Autonomous vs deferred* section above.
- **The librarian uses the memory substrate** with `source_agent="librarian"` for both Pre-Task Recall (`vault_search`) and Post-Session Persistence (`vault_extractFleetingFromTranscript`).

## Open questions

- Should the lint emit a cheap `dataview_blocks_present` annotation so the curator knows where to look, or is full-vault Dataview parsing on every pass acceptable?
- When the curator promotes from operator-invoked to a scheduled job, what's the trigger model — pure schedule, or "schedule + only if findings above threshold"?
