---
name: onboarding
description: Use when onboarding or re-auditing a project against Crew. Defaults to a read-only report; edits require explicit apply authorization. Preserves mature entry files, safety tripwires, delivery contracts, and runbook pointers.
tier: concept
requires: []
---

# Onboarding

Crew onboarding has two distinct modes: **audit** and **apply**. A plain request
such as “onboard this project” and an explicit audit request both select audit.
Audit is the default and writes nothing. Apply is available only when the current
run has a distinct, explicit authorization to apply onboarding changes.

The lifecycle rule is deterministic in `scripts/onboarding_contract.py`. Under a
supervised or autonomous host, bind any decision to that host's generic
escalation/decision interface. Do not assume synchronous chat and do not embed a
private supervisor protocol in a consumer project.

## Audit profile under a host

Under a supervising host, its task contract wins over this skill on reporting,
external writes and delivery (the reporting contract's host rule). Two things in
that contract shape onboarding, and both come from the session, never from a
repository setting:

- **Whether entry files are the host's to write.** A host that reserves
  `AGENTS.md` and `CLAUDE.md` for humans selects the **hosted** audit profile:
  audit still reports what those files carry, but proposes no merge into them.
  Pass `--audit-profile hosted` to every check; a missing or partial reporting
  section is `N/A` (the host supplies reporting), not drift. Moved-skill and
  Learning findings on an entry file are reported as facts, not proposed edits.
  Local-skill proposals (slot fills, the capability map) are unaffected.
- **Whether apply is available.** The host's task contract says so. When it does
  not say, apply is available in the standard profile, behind the host signal
  below, and unavailable in the hosted profile; an audit under a host that makes
  apply unavailable lists its proposals as the host's decisions, not as
  "run apply". `resolve_mode(profile=..., apply_available=...)` encodes both.

## The foundation stance

1. **Entry files drive behavior; skills carry reusable detail.** `AGENTS.md` and
   `CLAUDE.md` hold routing, posture, planning, memory, tripwires, fallback, and
   delivery boundaries. Project facts and conventions usually belong in local
   skills, but bootstrap-critical runbook pointers may stay near the code.
2. **Merge, never replace, mature entry files.** The template is a source of
   missing behavior, not authority to erase project contracts.
3. **Preserve safety and delivery.** Safety tripwires, project delivery gates,
   verification commands, protected-seam rules, and runbook pointers are
   load-bearing. Never remove or weaken them merely to make an entry file smaller.
4. **Trigger versus detail.** A silent landmine's trigger stays always-on; its
   detailed procedure can live in a skill or runbook. Preserve both sides of that
   link.
5. **Platform-first only on evidence.** Use a granted capability as the preferred
   path; degrade after an actual failure and report whether it was unavailable or
   simply not tested.

## Audit mode — always first, never mutating

### 1. Run Doctor

Run `doctor` read-only and consume its exact profile taxonomy:

- `personas` when repository evidence declares an OpenClaw/persona runtime;
- otherwise `platform` when a project capability was proven working;
- otherwise `portable`.

Keep Doctor's installation, enablement, runtime, and capability states separate.
Do not “fix” a missing or degraded result during audit.

### 2. Inventory behavioral surfaces

Read the root `AGENTS.md`, `CLAUDE.md`, contribution/delivery contracts, and
runbook indexes. Classify content without editing it:

- **behavior** — routing, autonomy, planning, memory, interface boundaries,
  tripwires, fallback, validation, and delivery;
- **facts/conventions** — candidates for a local skill when reusable;
- **accretion** — dated narrative or duplication that may be removable;
- **landmines** — silent-failure triggers whose pointer and consequence must stay
  visible;
- **preserved project contract** — mature safety, delivery, bootstrap, or runbook
  content that must remain even when it is detailed.

Long is not itself a defect. A mature entry file can legitimately contain more
behavior than `templates/AGENTS.md`. Never use byte count or “shorter” as a
success criterion.

### 3. Audit local ownership and layout

Derive only the slots the installed Crew skills actually declare in
`expects-local:`. Keep recommended names such as `litellm-access-map` and
`vault-ops` separate from required slots. Record the concern → local-skill owner
map; do not create a catalogue the runtime already supplies.

Canonical local skills live once at `.agents/skills/<name>/SKILL.md`. Claude can
consume directory symlinks at `.claude/skills/<name>`; Pi and Codex consume the
canonical `.agents/skills` tree from the project. Use the validator from the
absolute resolved Crew package root, not a consumer-relative `scripts/` path.
Validate `agents/`, `.claude/agents/`, and `.pi/agents/` frontmatter as well.

### 4. Audit gaps without proposing destructive shortcuts

For a project without `AGENTS.md`, report that apply mode would start from
`templates/AGENTS.md`, infer verification commands and repository facts, and
leave judgment slots with concrete suggestions. Do not create the file in audit.

The reporting contract is required spine, not optional template text: every
onboarded `AGENTS.md` carries the `## Reporting contract` section, so reports
lead with decisions from adoption rather than by per-session correction. Audit
it with `scripts/onboarding_contract.py --check-reporting <AGENTS.md>`; a
`MISSING` or `DEGRADED` result is a proposed addition. Under the hosted audit
profile, add `--audit-profile hosted`: the result is `N/A` and nothing is
proposed.

Skills that moved from Crew to a pack change their namespaced name. Audit each
entry file, local skill, and overlay with
`scripts/onboarding_contract.py --check-moved-skills <file>`: every
`crew:<skill>` it lists is a proposed update to `<pack>:<skill>`, and every hit is
a proposal to install that pack. Apply uses `rewrite_moved_skill_references`,
which changes only `crew:`-prefixed names; a bare name keeps pi's spelling.

The `agent-runtime` slot carries a `## Capabilities` table that maps each
capability skills name (`cli:`, `mcp:`, `external:`) to the tool that provides it
here, with a fallback command for the operator. Build it from the read-only
inventory: run `scripts/crew_inventory.py --project <repo> --format json` from the
resolved package root, piping the MCP servers and tools this session can see
with `--observations -`. Pass the result to `capability_map_proposal` with the
audit contract and the `templates/local-skills/agent-runtime.md` stub, then
report its action (`create`, `merge`, `unchanged` or `decision-needed`) and its
diff. Every capability it lists under pending removal is a proposed deletion.

Every other unfilled slot, Crew's or a pack's, gets a proposed local fill
`<project>-<slot>` built from its owner's stub. Pass the same inventory to
`pack_slot_proposals` with the contract, the resolved Crew root and a depth.
**Quick** is the default, and asks only what the pack's skills need to start:
sections marked `crew:optional` stay `▸ Fill`, and the skills use their defaults
and say so. **Thorough** asks every section. For each proposal:

- `human_sections` become a short interview, one question per section;
- for each of the `discoverable_sections`, run `learn` with the first of its
  `capabilities` the capability map shows as present (none present: ask it as a
  human section instead). It drafts
  that section as a proposal, and the operator promotes it. Never write a
  discovered fact into the fill directly;
- `complete` finishes a partial local fill in place. `decision-needed` (the owner
  is ambiguous, or there is no stub) goes to the host.

A slot a pack already fills gets no proposal. The marker grammar is in
docs/PACKS.md.

The `## Learning` section is optional spine: it declares where `learn` queues
proposals (docs/LEARNING.md). Audit it with
`scripts/onboarding_contract.py --check-learning <AGENTS.md>`. `N/A` means learn
stays report-only, which is a valid choice, so offer the section as an optional
addition and never report it as drift. `DEGRADED` means the declared queue is
unusable, for example under a `skills` directory. Under the hosted profile
`DEGRADED` stays `DEGRADED` and fails the check, with the fix left to the host;
only an absent section or queue is `N/A`.

For existing files, report what behavior is present, missing, duplicated, or
ambiguous. Propose moves as a mapping of source content → destination skill or
runbook → retained pointer. Flag every proposed deletion separately. Preserve
source attribution and compatibility notes that still explain a live contract.

### 5. Audit persona/OpenClaw consumers when present

The `personas` profile is a narrower consumption model: persona agents consume
only capability skills their grants can support; they do not inherit Crew roles
or the repo's root `AGENTS.md`. Inspect the project's actual install source,
allowlists, and capability grants in both directions.

Crew does not currently promise a bundled capability slice. Do not prescribe a
dead clone or invent a slice path. If the project needs a consumer-owned slice or
an outward-facing package decision, record that as a recommendation requiring
the host decision interface. Operator/deployment skills remain operator-only.

### 6. Deliver the audit and stop

Return a report with:

- Doctor profile and top action;
- observed behavior, facts, landmines, preserved contracts, and untested areas;
- proposed additions, moves, and removals as separate lists;
- exact validation commands the host project already owns;
- decisions required before apply.

If apply was not explicitly authorized, stop at this boundary. The report is the
result; do not create a plan file or modify the repository just to persist it.

## Apply mode — explicit authorization required

Apply only when apply is available (see *Audit profile under a host*), the
request distinctly says to apply the onboarding findings, and the supervising
host supplies a fresh, non-persisted authorization signal for
this exact invocation. The host verifies the decision and invocation identity;
Onboarding does not mint, authenticate, persist, or reuse authorization tokens.
A saved or standing decision, prior-run signal, prior audit, plain onboarding
request, or general autonomy is not apply authorization.

Before the first edit:

1. re-state the approved audit findings and exact files in scope;
2. confirm the host write boundary permits those files;
3. route destructive moves/removals through the host runtime's generic
   escalation/decision interface and wait for a recorded decision;
4. exclude user settings, plugin registries, deployed services, and other
   external state unless separately authorized.

Under the hosted profile, skip every entry-file merge below (the contract's
`proposes_entry_file_merges` is false) and write only local skills.
For a new project, merge the filled `templates/AGENTS.md` scaffold and optional
one-line `CLAUDE.md` shim. For a mature project missing the reporting contract, merge
the template's section with `ensure_reporting_contract` — it lands before the
tripwires and never replaces a project's own reporting section. For the capability
map, call `capability_map_proposal` with the apply contract and write its text to
its target. It changes only the text between the `crew:capability-map` markers and
keeps every Fallback cell the operator wrote. With no `agent-runtime` fill it
creates `<project>-agent-runtime` from the stub. A pack-provided fill is a host
decision. A vanished capability stays `absent` until its removal is authorized.
For each slot proposal with action `create`, write its `text` to its target, then fill in the
interview's answers. Discoverable sections stay `▸ Fill` until their `learn`
proposals are promoted.
When the operator accepts the optional Learning section, merge it with
`ensure_learning_section` the same way. For a mature project, edit surgically: preserve its
entry files, safety tripwires, delivery contracts, verification commands, and
runbook pointers. When moving detail, establish and validate the destination
first, retain an actionable pointer, then remove source text only if that
specific removal is authorized.

After edits, stop at the implementation handoff. Do not run layout/frontmatter
validators or project checks from Onboarding; hand validation, review, commit,
push, PR, and CI to the host project's established workflow. Do not declare the
wider change delivered merely because the onboarding edit or Doctor report looks
correct.

## Re-audit

Re-running onboarding returns to audit mode unless apply is explicitly authorized
again. Compare the new report with prior evidence; fewer findings are useful, but
idempotence and preserved behavior matter more than file size.
