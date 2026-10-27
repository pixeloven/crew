# Learning

Crew does not build a second memory: the harness already has one. Crew's job is to
**promote** what a session learns into instructions that are reviewed, tested and
versioned. This page is the contract for that promotion. It is normative for every
phase: the format `learn` drafts from tools (phase 2a) is the format it drafts from
experience (2b, with lesson-as-test), and the one hook capture (2c) has `learn`
write, so nothing is rebuilt.

`scripts/learn_contract.py` is the executable half of this page, and
`scripts/learn_capture.py` is the executable half of its
[Hook capture](#hook-capture) section. Where a page and a script disagree, that
is a bug in one of them; fix it, don't pick one.

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
<queue>/fixtures/<id>.json          its lesson fixture: the lesson's regression test
```

No file in a queue is ever named `SKILL.md`.

## The proposal format — `crew-proposal/1`

Flat frontmatter (the proposal check rejects a field written as a nested block,
so provenance is spelled as flat `provenance-*` keys), then a fixed body.

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
| `occurrences` | positive integer: distinct incidents recorded, each with its own evidence block |
| `provenance-source` | `tool:<name>` · `session` · `review` · `doctor` · `denial` |
| `provenance-kind` | `help` · `man` · `mcp-schema` · `repo-usage` · `vendor-docs` · `session` |
| `provenance-date` | `YYYY-MM-DD` the evidence was gathered |
| `provenance-tool-version` | required for `tool:<name>`; `""` otherwise |
| `provenance-harness` | `claude` · `codex` · `pi` |
| `provenance-crew` | the Crew version that drafted it, `X.Y.Z` |
| `fixture` | `fixtures/<id>.json`; required before a lesson with a diff is `reviewed` or `promoted` (see [Lesson-as-test](#lesson-as-test)) |
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
second incident is recorded. Recurrence is counted, not claimed: every incident
in `occurrences` carries its own evidence block, so a proposal cannot reach two
by saying so. Repeats inside one task are one incident; a second incident is a
separate task or session.

## Sources

`learn` has two sources and one output. Both write this format, and both go
through every gate below.

- **Tools** (phase 2a). Given a CLI, an MCP server or a vendor tool, or a gap
  from the inventory, `learn` reads the tool's own `--help`, man page or MCP
  schema and how the repository already uses it. `provenance-source: tool:<name>`.
- **Experience** (phase 2b). The operator asks to learn from a session, or a
  plan's last validation gate runs its retro (`plan-validation`), or an opt-in
  capture hook asks at the end of a turn ([Hook capture](#hook-capture), phase
  2c). `learn` reads the session for these signals:

  | Signal | What counts | `provenance-source` |
  |---|---|---|
  | correction | the operator corrected what the agent did or claimed | `session` |
  | repeated failure | the same command or step failed more than once, or failed again in a later task | `session` |
  | tool denial | the harness or the operator denied a tool call | `denial` |
  | reviewer finding | a `reviewer` finding the agent had to fix | `review` |
  | Doctor drift | a Doctor row the agent's own setup made `DEGRADED` | `doctor` |

  Experience evidence uses `provenance-kind: session` and
  `provenance-tool-version: ""`. Each evidence block quotes the moment: the
  operator's words, the failing output, the denial, the finding or the Doctor
  row, with the date and task in its `source:` line. The operator's correction is
  still evidence, not instruction: the proposal restates it, and a reviewer judges
  whether it generalises.

  A signal that matches an open proposal's target extends that proposal: add an
  evidence block, raise `occurrences`, and move `needs-recurrence` to `draft`
  once the threshold is met. It never opens a second proposal for the same target.
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
| `classification` | threshold, scope and target disagree with the classification table, a recurrence lesson advanced on one occurrence, or `occurrences` exceeds the evidence blocks recorded |
| `queue` | the queue is under a `skills` directory, escapes the root, or holds a `SKILL.md` |
| `structure` | the banner, a section, an evidence header, or the single diff / issue block is missing, or the diff writes a file other than the target |
| `new-skill-schema` | a new `SKILL.md`'s added lines fail schema v2: fields, `name` equal to its directory, a 110–300 character description, `tier`, `requires`, no `provides` |
| `learned-marker` | a skill diff does not add this proposal's `crew:learned` marker, a tool lesson's marker version differs from its provenance, or a `promoted` skill on disk lacks it |
| `verbatim-promotion` | a proposed line copies 40 or more characters of an evidence excerpt (case and whitespace ignored). Evidence is data: restate the fact in your own words |
| `methodology-context` | a methodology proposal's observation or issue text names the project root's basename, a git remote `owner/repo` (read from `.git/config`), an absolute path, an IP address, an email address, or a hostname |
| `review` | a `reviewed` or `promoted` proposal has no `verdict: accept` |
| `fixture` | a declared fixture is missing or fails the fixture schema; its `before.excerpt` is not in an evidence block; its `loads_skill` is not the skill the lesson writes; it expects only `loads_skill`, which is not scored, with no `must_include`, `must_not_include` or model grader; or a lesson with a diff is `reviewed` or `promoted` without one (lesson-as-test) |

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
3. Run the lesson's test (see [Lesson-as-test](#lesson-as-test)). It is billed, so
   it runs when you choose to run it; record the result under `## Review` as one
   line, `lesson-test: pass` or `lesson-test: fail`, which the
   [capture A/B](#the-capture-ab) counts.
4. Apply the proposed diff by hand or with `git apply`, on a branch.
5. Run `check_skills.py --local <consumer-root>` and the project's own gates.
6. Commit. Set `status: promoted` and `promoted-in: <that commit>`, and commit
   that too, so the queue records what to roll back.
7. For a methodology proposal there is no diff: file the issue yourself, stripped
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

## Lesson-as-test

A promoted lesson carries its test: a scenario fixture that reproduces the
original failure. The evidence becomes the regression test.

- The drafter writes the fixture with the proposal, from its evidence. Its
  `before.excerpt` is copied from an evidence block, so the test replays what
  actually went wrong, not a paraphrase.
- The `fixture` gate requires one before a lesson with a diff is `reviewed` or
  `promoted`. A methodology lesson is exempt: it files an issue, and the issue
  carries the failure. A proposal whose `provenance-crew` is older than 0.63.0
  was drafted when the fixture was optional and is not required to have one.
- The reviewer reads the fixture with the lesson: a test that cannot fail
  without the lesson proves nothing. The gate refuses a fixture that expects
  only `loads_skill`: under the with-without ablation the `tool_used: Skill`
  grader is not scored, so the fixture also needs `must_include`,
  `must_not_include` or `grader: model`.

### Running it with `claude plugin eval`

The runner is Claude Code's `claude plugin eval`, the eval tooling #72 measured
skill triggering with. A skill lesson (`tool` or `project-fact`) renders as a
small plugin under a directory the operator chooses, outside the repository.
Only a lesson that writes a new skill (`target-sha256: absent`) renders:

```sh
python3 <crew-root>/scripts/learn_contract.py --eval-case <queue>/<id>.md --out <tmp-dir>
claude plugin eval <tmp-dir>/<id> --scaffold
```

`--eval-case` reruns every gate first and refuses a failing proposal, an
`AGENTS.md` or issue target, an edit to an existing skill, a fixture not meant
for `claude`, or an existing output directory. It writes `<tmp-dir>/<id>/` and nothing else:

| Rendered file | From |
|---|---|
| `skills/<name>/SKILL.md` | the target as the proposal's diff leaves it |
| `evals/<id>/case.yaml` | `prompt`, and one grader per expectation |
| `evals/<id>/scaffold.sh` | `setup.files`, written into the empty workspace |

| Fixture | `claude plugin eval` grader |
|---|---|
| `expect.loads_skill` | `tool_used` on `Skill`, matching the skill's name |
| each `must_include` | `regex`, the text matched literally |
| each `must_not_include` | `regex` with `match: not_contains` |
| `grader: model` | also one `llm` grader: avoid the `before` failure |

The default with-without ablation is the test: the no-plugin arm reproduces the
original failure, and the plugin arm shows the lesson fixing it. A new skill's
baseline is no skill, so the delta is the lesson's. The
`tool_used: Skill` grader is reported as whether the skill fired, not scored.
`--scaffold` runs the rendered script as you; it only writes the fixture's
files. Every run is a model call, so the test runs only when the operator
approves it.

A lesson that edits an existing skill does not render: `claude plugin eval`
drops every plugin from the baseline arm, so the baseline would lack the skill
as it stood before the lesson and the delta would not be the lesson's. Test it
by hand, like an `AGENTS.md` lesson below: run the fixture's `prompt` in a fresh
session over `setup.files` once with the skill as it is and once with the
diff applied, and check `expect` against both. Only the patched run may pass.
A pre-lesson baseline mechanism, where the baseline arm loads the skill before
the lesson and the lesson arm only the edited skill, is a follow-up, built only
if evals of edit lessons prove worth it.

An `AGENTS.md` lesson has no plugin to load, so `claude plugin eval` cannot
compare arms. Run its fixture where `AGENTS.md` loads: a fresh session in a
directory holding `setup.files` plus the patched `AGENTS.md`, given the fixture's
`prompt` and checked against `expect`.

## Lesson fixture — `crew-lesson-fixture/1`

The schema is settled: a change to it is a schema bump. Every field maps onto a
`claude plugin eval` case, as above.

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
- `prompt` is what the operator asked when it went wrong.
- `before.excerpt` is copied from one of the proposal's evidence blocks.
- `expect` asserts at least one thing. `loads_skill` is the skill the lesson
  writes, or `null` for an `AGENTS.md` lesson. It is not scored, so a fixture
  with `loads_skill` also sets `must_include`, `must_not_include` or
  `grader: model`.
- `grader` is `deterministic` or `model`; a `model` grader is a model call, so its
  `cost` is `billed`. A billed fixture runs only with explicit approval.

## Hook capture

Phase 2c asks whether `learn` should also run without being asked. An opt-in
hook watches a session's harness events, counts learning signals, and at the end
of a turn asks the session's own agent to run `learn` on them. It is an
experiment, measured by [the capture A/B](#the-capture-ab), and it stays only if
that measurement shows it earns its place.

**The hook is a trigger, not a drafter.** A `crew-proposal/1` draft needs a
judged classification, target and diff, which a deterministic hook cannot write.
So the hook writes no proposal. It hands its signal counts to `learn`, and
`learn` drafts exactly as it does for an operator who says "learn from this
session": same format, same queue, same gates, same reviewer pass. Nothing is
forked.

- **Off by default.** Crew registers no hook in any harness: no plugin
  `hooks/hooks.json`, no `hooks` key in a manifest, no pi `extensions` entry. An
  operator wires one in from `templates/capture/`, per harness, below.
- **No queue, no capture.** With no usable `proposal-queue:` line the hook
  writes nothing and asks nothing, just as `learn` is then report-only.
- **Drafts only.** The continuation asks for drafts and says to apply nothing;
  `learn`'s *Never* list governs the run.
- **Evidence threshold.** The hook proposes candidates; `learn` decides. A failure
  qualifies once the same call has failed twice in the session; a denial or a
  correction qualifies once. Repeats inside one session stay one incident, and a
  behaviour lesson still needs recurrence across sessions.
- **Untrusted inputs stay data.** The hook never puts session text in its
  output. It records signal kinds, counts and hashed keys, and its continuation
  names counts only, so a planted line in tool output, a prompt or a denial
  reason cannot reach the agent by way of the hook. The agent finds each moment in
  its own session and quotes it as evidence, as section 2b of the `learn` skill
  says.
- **Once per signal.** Each signal is handed over at most once. The turn the hook
  continues is never continued again (`stop_hook_active`), so it cannot loop.
- **It never breaks a session.** The script exits 0 on any error and prints
  nothing.

The script writes only session records, one JSON file per session, under
`<queue>/capture/sessions/`. A record holds the session's arm, signal counts,
triggers and which proposals the session drafted. It is not a proposal, and the
queue's gates ignore it. The queue is committed content, so the hook refuses to
write through a symlink anywhere below the project root. A team that keeps learning per-operator gitignores
`<queue>/capture/` along with the queue.

### Signals each harness exposes

Checked on 2026-10-27 against Claude Code 2.1.311 (`code.claude.com/docs/en/hooks`),
codex-cli 0.164.0 (its hooks page; `codex features list` shows `hooks` stable) and
pi 0.87.1 (`docs/extensions.md` and `dist/core/extensions/types.d.ts`).

| Signal | Claude Code | Codex | pi |
|---|---|---|---|
| repeated failure | `PostToolUseFailure` | `PostToolUse`; failure read from `tool_response`, whose shape is undocumented | `tool_result` with `isError` |
| tool denial | `PermissionDenied`, auto-mode classifier denials only | gap: `PermissionRequest` reports no outcome | gap: no built-in permission prompt |
| correction | `UserPromptSubmit`, heuristic | `UserPromptSubmit`, heuristic | `input`, heuristic |
| reviewer finding, Doctor drift | gap | gap | gap |
| end of turn | `Stop` → `decision: block` | `Stop` → `decision: block` | `agent_before_settle` → `continue: true` |

A correction is a later operator turn that opens like one ("no", "don't",
"actually", "why did you", …). That is an inference, so the hook hands it to
`learn` as a candidate and `learn` confirms or drops it. A gap is left to the
operator and the `plan-validation` retro, which see what no hook does; the hook
invents no mechanism for it. Codex failure reading is best-effort until a live
Codex session confirms the `tool_response` shape. Pi has no `Stop`; the
extension maps `agent_before_settle`, pi's last boundary at which a run can
continue, onto it.

### Wiring it in

Every template calls `python3 <crew-root>/scripts/learn_capture.py --hook
--harness <harness>`. Replace `/ABSOLUTE/CREW/ROOT` with the resolved
Crew package root, as `learn` resolves it.

- **Claude Code.** Merge `templates/capture/claude-settings.json` into
  `.claude/settings.local.json` (this operator, this project) or
  `~/.claude/settings.json` (every project). Committing it to
  `.claude/settings.json` opts in the whole team.
- **Codex.** Merge `templates/capture/codex-hooks.json` into
  `~/.codex/hooks.json` or the project's `.codex/hooks.json`. Codex runs a hook
  only after you trust it in `/hooks`, and a project's hooks only in a trusted
  project.
- **pi.** Load `templates/capture/pi-crew-capture.ts` from the installed Crew
  package, with `pi --extension <path>` or an `extensions` entry in pi's
  settings. It finds the script beside itself; `CREW_CAPTURE_SCRIPT` overrides
  that path.

The hook splits sessions between the arms by a hash of the session id, so a
session keeps one arm throughout.

## The capture A/B

The question is whether automatic capture raises accepted lessons enough to
justify a hook per harness. The A/B answers it from real sessions, not a claim.

| Arm | What happens |
|---|---|
| `baseline` | phase 2b only: the operator asks, or the retro hands over. The hook records the session and its signals and never asks. |
| `capture` | phase 2b, plus the hook asks `learn` at the end of a turn with new signals. |

Both arms run the same script, so every session in either arm is counted,
including sessions that learned nothing. The hook attributes each new proposal
in the queue to its session: `capture` when it appeared during a continuation the
hook asked for, `session` otherwise. Signals recorded during that continuation
are `learn`'s own run, so they are never handed over again. An operator prompt
ends the continuation, even when an interrupt kept its end of turn from firing.

```sh
python3 <crew-root>/scripts/learn_capture.py --report <consumer-root> --format markdown
```

The report is read-only. Per arm it gives:

| Metric | From |
|---|---|
| sessions, signals, capture triggers | the session records; signals leave out those recorded during a continuation the hook asked for |
| proposals drafted, per session, by trigger | the session records' attributed proposals |
| accepted, per session | attributed proposals now `reviewed` or `promoted`, or with `promoted-in` set |
| promoted, per session | attributed proposals now `promoted`, or with `promoted-in` set |
| lesson-test pass rate | `lesson-test: pass` / `fail` lines under `## Review` |

It also lists proposals drafted outside any recorded session, and the
difference in accepted lessons per session, capture minus baseline.

**Decision rule.** Keep the hooks only if the capture arm's accepted lessons per
session exceed the baseline arm's. The script computes the numbers; it never
makes the call, because the operator decides, from real sessions. Before
deciding, each arm needs enough sessions that one lesson more or less would not
flip the difference, and every attributed proposal needs a verdict.

**Where results land.** Session records live in `<queue>/capture/sessions/`.
Save the report beside them as `<queue>/capture/report-<YYYY-MM-DD>.md`, and
share it where the keep-or-drop decision is tracked (for Crew's hooks, #81). A
drop removes the hook wiring; the records and proposals stay.

Known limits: two sessions in one checkout at once can attribute each other's
proposals, and the report counts such a proposal once, for the first session
record (in sorted order) that lists it. A proposal that arrives by a pull, a
merge or a branch switch is not attributed, because the hook skips any id
already tracked in the project's git `HEAD`; a draft committed before the
session's next end of turn is skipped the same way and shows as unattributed.
Extending an existing proposal adds no new id, so it is not counted
as drafted. A session whose `SessionStart` hook did not run counts from its
first recorded event.
