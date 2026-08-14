---
name: vault-tools
description: Writing, indexing, and managing the lifecycle of vault notes — vault_writeNote, retrieval tracking, consolidation, orphan detection. Load when authoring, editing, searching, or curating notes via the vault.* MCP surface.
tier: subject
requires: [mcp:kb]
audience: [crew]
expects-local: [vault-ops]
---

This skill is the **tool surface** reference. Many corpora also keep a canonical conventions note inside the vault itself (e.g. a `notes/vault-conventions.md`); if the deployment keeps one, read it via `vault_readNote` before authoring anything non-trivial — that note is the **schema** reference for its corpus.

## Write Pattern

Write to the vault via `vault_writeNote`. Required fields: `kind`, `title`, `source_agent`, `tags` (≥1). Required only when `kind=research`: `recommendation`. Optional: `type`, `body`, `issue`, `pr`, `valid_from`, `valid_until`, `role`, `aliases`.

```
vault_writeNote(
  kind="research",        # REQUIRED — see Kinds table
  type="person",          # optional structural shape — see Types
  title="<descriptive title>",
  body="<structured content>",   # if None, vault template auto-fills
  tags=["domain:litellm", "project:track-2"],
  recommendation="...",   # REQUIRED when kind=research
  source_agent="researcher",
  issue=42,
  valid_until="2026-12-31",
)
→ {note_path, filename, vault_root, id, index_status, linksCount, tagsCount}
```

`vault_writeNote` **auto-indexes** the note on emit. No separate `indexNote` call needed in normal flow. Wikilinks to not-yet-written targets are safe (no FK constraint on link targets). Exact feature availability depends on the deployed vault-mcp version.

Notes auto-route by kind: `fleeting` → `fleeting/`, `agent-run` → `archive/agent-notes/`, everything else → `notes/` (flat — no subdirectories).

## Two-axis schema — `kind` + `type`

| Axis | Required? | Drives | Values |
|------|-----------|--------|--------|
| `kind` | yes | directory routing, body template, lifecycle role | 10-value enum below |
| `type` | optional | Dataview projections, structural-shape filtering | 5-value enum below |

A research note about a persona: `kind=research, type=person`. A runbook for a specific service: `kind=runbook, type=reference`. The corpus's own conventions note, if the deployment keeps one, may refine these further.

### Kinds (10-value enum)

| Kind | Purpose | Body template (auto when body=None) |
|------|---------|-------------------------------------|
| `note` | Evergreen general knowledge | Free-form (body required) |
| `fleeting` | Unprocessed capture / inbox | Free-form (body required) |
| `research` | Option analysis, evaluations | Context → Options → Recommendation → Open questions |
| `runbook` | Operational procedure | Symptoms → Diagnosis → Fix → Verification |
| `decision` | Explicit ADR | Context → Decision → Alternatives → Consequences |
| `architecture` | System design | Problem → Architecture → Trade-offs → Out of scope |
| `convention` | Coding / platform standard | Scope → Rules → Examples → Exceptions |
| `review` | PR / spec / vault review | Scope → Findings → Recommendation → Action items |
| `credential` | Service credential doc | Service → How to obtain → Where used → Rotation |
| `agent-run` | Agent execution record | Goal → Actions → Outcome → Follow-ups |

`note` and `fleeting` are **free-form** — they reject `body=None`. The other 8 kinds auto-inline a template from `_meta/templates/<kind>.md` (operator-curated) or fall back to a built-in section skeleton.

### Types (5-value enum, optional)

| Type | Purpose |
|------|---------|
| `concept` | Evergreen claim, one idea per note |
| `moc` | Map of Content — curated index into a topic cluster |
| `person` | Persona / individual / contact |
| `reference` | External citation, runbook reference |
| `log` | Event / observation / dated entry |

## Tag taxonomy

Tags accept three styles (in increasing structure):

- **Flat** — `litellm`, `multi-agent`. Always valid. Topic-level.
- **Namespaced** — `domain:infrastructure`, `project:track-2`. Recommended when the axis matters. Controlled `domain:*` vocab: `technical | creative | business | research | design | infrastructure | operations`.
- **Reserved** — `kind:*` auto-appended by vault-mcp; `status:*` reserved. Do not author.

### What writeNote rejects at emit (raises ValueError)

- Empty title or empty tags list
- Unknown `kind`, `type`, or `source_agent`
- `kind=research` without `recommendation`
- `body=None` on a free-form kind (`note`, `fleeting`)
- **Tag artefacts**: numeric-only tags (`^\d+$` — GitHub issue refs) and 6-char hex (`^[A-Fa-f0-9]{6}$` — colour codes). These are scanner false-positives.

### What writeNote warns on (soft, never blocks)

Every `vault_writeNote` and `vault_indexNote` response carries a `lint_warnings: list[{code, message}]` field. Empty list when clean. Categories:

- **`missing_section`** — body is missing a `## Section` heading expected for its kind (e.g. a `kind=runbook` without `## Verification`). Free-form kinds (`note`, `fleeting`) and unknown kinds produce no missing-section warnings.
- **`tag_synonym`** — a tag has a known canonical form. Current pairs: `k8` → `k8s`, `k8s` → `kubernetes`, `gh` → `github`, `tf` → `terraform`, `iac` → `infrastructure`.
- **`kind_tag_duplication`** — caller passed the `kind` value as a tag explicitly. vault-mcp auto-appends `kind`, so authoring it is noise. (writeNote only; `indexNote` skips this lint because it sees post-write state.)

Writes always succeed. Surfacing the warnings is the caller's responsibility.

## Tool surface — everything under `vault.*`

One MCP prefix covers reads, writes, search, metadata, and lifecycle.

### Read

- `vault_readNote(path, frontmatter_only=False)` → raw note content + frontmatter
- `vault_readNotes(paths)` → batch read multiple notes
- `vault_getNote(path)` → note with vault-mcp's schema metadata
- `vault_getBacklinks(path)` → notes linking *to* a given note
- `vault_getLinks(path)` → wikilinks + backlinks
- `vault_listVault(directory=None)` → directory listing
- `vault_listHeadings(path, level=None)` → Markdown headings in a note

### Search

- `vault_search(query, mode="semantic", limit=10)` → qmd vector search (use natural-language questions)
- `vault_search(query, mode="keyword", limit=10)` → BM25 full-text search (supports `"quoted phrases"` and `-negation`)
- `vault_findByTag(tag)` → notes carrying a tag (use for kind-based discovery: `tag="research"`, `tag="runbook"`)
- `vault_findByIssue(issue_number)` → notes linked to a GitHub issue
- `vault_findBrokenLinks(directory=None)` → wikilinks pointing at non-existent notes

### Write

- `vault_writeNote(...)` → emit + auto-index (see Write Pattern above)
- `vault_editNote(path, content)` → overwrite a note's content (re-index manually with `vault_indexNote(path)` afterwards — the proxy doesn't auto-sync the vault-mcp DB)
- `vault_appendToSection(path, heading, content)` → append to a section identified by its Markdown heading
- `vault_deleteNote(path, confirm)` → delete a note (`confirm` must match the bare filename, e.g. `"foo.md"`)
- `vault_indexNote(path)` → re-index after out-of-band edits

### Metadata

- `vault_getFrontmatter(path)` → frontmatter as JSON
- `vault_updateFrontmatter(path, updates)` → merge frontmatter updates
- `vault_addTags(path, tags, location="frontmatter")` / `vault_removeTags(path, tags, location="both")`

### Lifecycle + corpus health

- `vault_recordRetrieval(note_id)` → record access — call for every note you read to maintain corpus health signal
- `vault_findOrphans(status?)` → notes with no inbound links
- `vault_findStale(min_age_days?, max_retrievals?)` → notes not accessed recently
- `vault_findExpiring(days?)` → notes where `valid_until` falls within N days
- `vault_invalidate(note_id, reason)` → mark superseded (temporal supersession, not deletion)
- `vault_logConflictCheck(path)` → record conflict-check ran
- `vault_recordReviewDecision(path, decision, notes?)` → record consolidation outcome
- `vault_getConsolidationCandidates()` → fleeting notes ready for review
- `vault_findSkipped()` → fleeting notes skipped in past consolidation

## Transcript extraction (Post-Session Persistence)

```
vault_extractFleetingFromTranscript(
    messages=[{"role": "user"|"assistant", "content": str}, ...],
    source_agent="<your_role>",
    promote_intent=False,
)
→ {extracted: int, note_paths: [...], source_agent, model}
```

Calls the deployment's configured extraction model (`EXTRACTION_LLM_MODEL`), asks for 0–5 durable facts as JSON, and writes each fact as a `kind: fleeting` note through the standard write path. Best-effort — LLM failures return `error: ...` with `extracted: 0` rather than raising.

When `promote_intent=True`, every extracted note carries the signal so the deployment's promote job picks it up for operator review.

## Consolidation Pattern

Fleeting notes accumulate in `fleeting/` as the inbox. Run a periodic human review pass over `vault_getConsolidationCandidates()` (some projects wire a project-local slash command for this flow). For each candidate the operator decides:

- **Promote** → move the fleeting note into `notes/` with a permanent `kind:` (decision, runbook, research, etc.), or rewrite via `vault_writeNote` and delete the fleeting source.
- **Discard** → `vault_deleteNote(path, confirm=<filename>)` or strip the `promote-intent` signal so it stops surfacing.
- **Defer** → leave in `fleeting/`; the deployment's promote job re-surfaces it next cycle if the signal is still set.

Use `vault_recordReviewDecision(path, decision)` to log the outcome. `vault_getConsolidationCandidates()` returns the current queue.

## Daily Review Notes

Deployments typically schedule two recurring jobs (K8s CronJobs) that emit `kind=review` notes to `notes/` once per day — names and schedules live in the project's vault-ops local skill. Operator/lead triage closes the loop in each case.

- **Lint job** — vault-wide health scans (broken wikilinks, tag artefacts, missing `kind`, `kind=research` without `recommendation`, deprecated frontmatter fields, unparseable frontmatter, orphans, stale). One note titled `Daily vault lint — <YYYY-MM-DD>`. Findings capped at 20, sorted HIGH → MED → LOW.
- **Promote job** — vault-native. Scans `<vault>/fleeting/*.md` for the promote-intent signal (either `promote_intent: true` in frontmatter or the `promote-intent` tag), groups by `source_agent`, writes one note titled `Daily promote candidates — <YYYY-MM-DD>` listing flagged candidates per agent. Operator triages by moving notes into `notes/` (promote) or deleting/clearing the signal (discard).

Triage with `vault_findByTag(tag="lint")` or `vault_findByTag(tag="promote")`, or read recent `notes/` by date.

## Auth

All calls route through LiteLLM MCP. Agent VKs hold the consumer's read-access group (as `mcp_access_groups`), capped by its team allowlist — the concrete access group + team live in your platform's LiteLLM access-map skill; the generic mechanism is `litellm-routing-model`.
