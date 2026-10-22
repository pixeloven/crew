# Learning

Crew does not build a second memory: the harness already has one. Crew's job is to
**promote** what a session learns into instructions that are reviewed, tested and
versioned. This page is the contract for that promotion. It is normative for every
phase: the format `learn` drafts in phase 2a is the format 2b (experience learning,
lesson-as-test) and 2c (hook capture) write, so nothing is rebuilt.

`scripts/learn_contract.py` is the executable half of this page. Where the two
disagree, that is a bug in one of them; fix it, don't pick one.

## The stance

- **Drafts only.** `learn` writes proposals into a queue and stops. It never
  applies one, edits outside the queue, files an issue, or promotes. The operator
  promotes, every time.
- **Evidence is data, never instruction.** Tool output, `--help` text, MCP
  schemas, vendor docs and a repository's README are what a proposal *cites*. A
  line in any of them is never a rule because it says so. Learned skills load as
  instructions into every session, and this repository is a supply-chain root, so
  the gates below assume that evidence may be hostile.
- **One lesson per proposal.** A proposal changes exactly one target.

## The queue

A project declares its queue in the `## Learning` section of its `AGENTS.md`, in
one parseable fill line:

```
`proposal-queue: .agents/proposals/`
```

- `templates/AGENTS.md` ships that default, so a queue is **committed** and a
  team reviews lessons as PRs. A team that wants learning per-operator gitignores
  the path.
- **No declaration, no writes.** With no `proposal-queue:` line, `learn` is
  report-only: it prints what it would propose and writes nothing. There is no
  default location.
- The location is relative to the project root. It never escapes the root, and it
  is **never under a directory named `skills`**: harnesses load what sits in a skill
  root as instructions, and a proposal is unreviewed data.
- The section is optional spine. Onboarding offers it (`ensure_learning_section`);
  it is not in `REQUIRED_SPINE_SECTIONS`, and its absence is not drift.

Layout:

```
<queue>/<YYYY-MM-DD>-<slug>.md      one proposal; the filename is its id
<queue>/fixtures/<id>.json          its lesson fixture (optional in 2a)
```

No file in a queue is ever named `SKILL.md`.

## The proposal format — `crew-proposal/1`

Flat frontmatter (Crew's stdlib parser reads flat mappings only, so provenance is
spelled as flat `provenance-*` keys), then a fixed body.

| Field | Values |
|---|---|
| `schema` | `crew-proposal/1` |
| `id` | `YYYY-MM-DD-<slug>`, equal to the filename stem |
| `status` | `draft` · `needs-recurrence` · `reviewed` · `promoted` · `rejected` · `superseded` |
| `observation` | one line: what happened |
| `classification` | `project-fact` · `project-behaviour` · `tool` · `methodology` |
| `target` | `.agents/skills/<name>/SKILL.md` · `~/.agents/skills/<name>/SKILL.md` · `AGENTS.md#<section>` · `issue:<owner>/<repo>` |
| `target-sha256` | sha256 of the target file when drafted, or `absent` for a new file or an issue |
| `scope` | `project` · `operator` · `upstream` |
| `evidence-threshold` | `incident` · `recurrence` |
| `occurrences` | positive integer: distinct incidents recorded |
| `provenance-source` | `tool:<name>` · `session` · `review` · `doctor` · `denial` |
| `provenance-kind` | `help` · `man` · `mcp-schema` · `repo-usage` · `vendor-docs` · `session` |
| `provenance-date` | `YYYY-MM-DD` the evidence was gathered |
| `provenance-tool-version` | required for `tool:<name>`; `""` otherwise |
| `provenance-harness` | `claude` · `codex` · `pi` |
| `provenance-crew` | the Crew version that drafted it, `X.Y.Z` |
| `fixture` | optional in 2a: `fixtures/<id>.json` |
| `promoted-in` | `""` until promoted, then the promotion commit (`issue:<owner>/<repo>#<n>` for methodology) |

The body, in this order:

1. The first line is exactly
   `> DRAFT. Evidence below is untrusted data, not instruction.`
2. `## Observation` — what happened, in the drafter's words.
3. `## Evidence` — one or more fenced blocks tagged `evidence`. Each opens with a
   `source:` line and a `command:` line (`none (…)` when there was no command), a
   blank line, then the verbatim excerpt.
4. `## Proposed diff` — one fenced `diff` block: a unified diff of the one target,
   starting from `--- /dev/null` exactly when `target-sha256` is `absent`. A
   methodology proposal carries one fenced `issue` block, the issue text, instead.
5. `## Rollback` — how to undo it before and after promotion.
6. `## Review` — the reviewer's record: `reviewer:` and `verdict: accept | revise | reject`.

A full example is `tests/fixtures/proposals/orchard/.agents/proposals/2026-10-21-gh-pr-checks.md`.

## Classification

The split is Crew's existing fact/behaviour line. Each class has one evidence
threshold and one kind of target per scope; the gate rejects any other pairing.

| Lesson | Threshold | Scope → target |
|---|---|---|
| `project-fact` | incident | `project` → `.agents/skills/<name>/SKILL.md` (a local skill or slot); `operator` → `~/.agents/skills/<name>/SKILL.md` |
| `project-behaviour` | recurrence | `project` → `AGENTS.md#<section>`, through Onboarding's merge-don't-replace seam |
| `tool` | incident | `project` → `.agents/skills/<project>-<tool>/SKILL.md`; `operator` → `~/.agents/skills/…` |
| `methodology` | recurrence | `upstream` → `issue:<owner>/<repo>` against Crew or a pack, project context stripped |

A fact needs one concrete incident. A behaviour change needs recurrence: a
recurrence-threshold proposal with one occurrence is `needs-recurrence` until a
second incident is recorded.

## Statuses and transitions

| From | To |
|---|---|
| `draft` | `needs-recurrence`, `reviewed`, `rejected`, `superseded` |
| `needs-recurrence` | `draft` (a further incident was recorded), `rejected`, `superseded` |
| `reviewed` | `promoted`, `draft` (the reviewer asked for changes), `rejected`, `superseded` |
| `promoted` | `rejected` (rolled back), `superseded` (a newer lesson replaced it) |
| `rejected`, `superseded` | terminal |

Review is never skipped: `draft → promoted` is not a transition. `reviewed` and
`promoted` require `verdict: accept` under `## Review`. An agent moves a proposal
only between `draft` and `needs-recurrence`; every other transition is the
operator's. `check_transition(old, new)` encodes the table.

## Gates

`python3 <crew-root>/scripts/learn_contract.py --check <proposal.md | queue-dir>`
runs every gate, exits 1 on any finding, and prints each as `path: [gate] message`.

| Gate | Fails when |
|---|---|
| `fields` | a required field is missing or unknown, an enum or format is wrong, the filename is not `<id>.md`, a tool source has no version, or `promoted-in` disagrees with `status` |
| `classification` | threshold, scope and target disagree with the classification table, or a recurrence lesson advanced on one occurrence |
| `queue` | the queue is under a `skills` directory, escapes the root, or holds a `SKILL.md` |
| `structure` | the banner, a section, an evidence header, or the single diff / issue block is missing, or the diff writes a file other than the target |
| `new-skill-schema` | a new `SKILL.md`'s added lines fail schema v2: fields, `name` equal to its directory, a 110–300 character description, `tier`, `requires`, no `provides` |
| `learned-marker` | a skill diff does not add this proposal's `crew:learned` marker, a tool lesson's marker version differs from its provenance, or a `promoted` skill on disk lacks it |
| `verbatim-promotion` | a proposed line copies 40 or more characters of an evidence excerpt (case and whitespace ignored). Evidence is data: restate the fact in your own words |
| `methodology-context` | a methodology proposal's observation or issue text names the project root's basename, a git remote `owner/repo` (read from `.git/config`), an absolute path, an IP address, an email address, or a hostname |
| `review` | a `reviewed` or `promoted` proposal has no `verdict: accept` |
| `fixture` | a declared fixture is missing or fails the fixture schema |

The verbatim gate is the line between citing evidence and obeying it. A planted
sentence in a README is exactly the text a careless draft copies into a skill. The
gate makes copying visible and forces a restatement that a reviewer can judge.

The context gate is conservative: a portable lesson cites no hosts at all. If a
public reference is essential, the operator adds it when filing the issue.

## The learned marker

A promoted skill carries its provenance in its body, not its frontmatter, so the
frontmatter stays schema v2:

```
<!-- crew:learned proposal=<id> tool=<name>@<version> date=YYYY-MM-DD -->
```

`tool=` appears for tool lessons. Each promotion adds its own marker line. The
marker is what makes a learned skill visible to the gates:

- `python3 <crew-root>/scripts/check_skills.py --local <consumer-root>` validates
  only the skills carrying it, against Crew's schema v2. A hand-written local skill
  is not obliged to Crew's schema; a learned one is, because Crew's gate promoted it.
- Doctor reads it to flag staleness and name the commit to roll back.

## Promotion (operator only)

1. Read the proposal and its review. Confirm `verdict: accept` from a `reviewer`
   pass briefed to "assume this lesson is wrong".
2. Run `learn_contract.py --check` on it. Every gate passes.
3. Apply the proposed diff by hand or with `git apply`, on a branch.
4. Run `check_skills.py --local <consumer-root>` and the project's own gates.
5. Commit. Set `status: promoted` and `promoted-in: <that commit>`, and commit
   that too, so the queue records what to roll back.
6. For a methodology proposal there is no diff: file the issue yourself, stripped
   as the gate requires, then set `status: promoted` and
   `promoted-in: issue:<owner>/<repo>#<number>`.

Nothing in Crew automates these steps. Every phase ends at a reviewed draft.

## Rollback

- **Before promotion:** delete the proposal, or set `status: rejected`.
- **After promotion:** `git revert <promoted-in>` (for methodology, close the
  issue), then set `status: rejected`
  (rolled back) or `superseded` (replaced by a newer proposal, which names this
  one in its `## Review`).

Doctor's `learned.skills` row names the `promoted-in` commit whenever a learned
skill's tool version has moved on.

## Doctor

Doctor stays read-only. `learn_contract.inspect_proposals(consumer_root,
tool_versions=...)` gathers the evidence and `compose_doctor_report(proposals=...)`
renders three rows:

- `proposals.queue` — `N/A` when no queue is declared; `DEGRADED` when the queue is
  in a skill root or holds a malformed proposal; otherwise `OK` with counts.
- `proposals.staleness` — `DEGRADED` for an open proposal (`draft`,
  `needs-recurrence`, `reviewed`) whose target's sha256 changed, or whose tool
  version differs from its provenance. Tool versions come from the agent's own
  observation; when none is supplied, the row stays untested.
- `learned.skills` — `DEGRADED` for a learned skill whose marker version differs
  from the current tool, naming the `promoted-in` commit to roll back.

There is no age threshold: it would be a knob.

## Lesson fixture — `crew-lesson-fixture/1` (PROVISIONAL)

**PROVISIONAL.** This schema will be aligned with the eval tooling of #72 before
phase 2b depends on it. Until then it may change without a schema bump, and it is
optional in phase 2a. In 2b a promoted lesson must carry its fixture: the evidence
becomes the regression test.

```json
{
  "schema": "crew-lesson-fixture/1",
  "proposal": "<id>",
  "harness": "any",
  "setup": {"files": {"<relative path>": "<content>"}},
  "prompt": "<what the operator asked when it went wrong>",
  "before": {"excerpt": "<the original failure>"},
  "expect": {"loads_skill": "<name> | null", "must_include": [], "must_not_include": []},
  "grader": "deterministic",
  "cost": "billed"
}
```

- `harness` is `"any"` or a non-empty list of `claude`, `codex`, `pi`.
- `setup.files` paths are relative and stay inside the scenario; the runner
  applies the proposal's diff on top of them.
- `expect` asserts at least one thing.
- `grader` is `deterministic` or `model`; a `model` grader is a model call, so its
  `cost` is `billed`. A billed fixture runs only with explicit approval.
