# Changelog

Release notes for each version, newest first. Every version bump adds its
section here in the same PR. Earlier releases are described in their pull
requests and tags.

From 0.57.1 on, every version's section opens with a `### Consumer impact`
section. It always lists the same three items, and an item with nothing to
report says "None":

- **Renamed or moved:** each skill or role that changed its name or home, as
  `old name -> new home`.
- **Removed:** each skill or role that is gone.
- **Action needed:** each contract change a consumer must act on before
  bumping, such as slots, frontmatter, or peer floors.

A consumer who pins a tag reads this section in every release between their
pin and the new tag to decide whether the bump is safe. The other sections
(`Added`, `Changed`, `Fixed`) carry the full detail. Older sections predate the
convention and are not backfilled.

## 0.63.0

### Consumer impact

- **Renamed or moved:** None.
- **Removed:** None.
- **Action needed:** Before you set a lesson drafted by Crew 0.63.0 or later
  to `reviewed` or `promoted`, give it a fixture, unless it is a methodology
  lesson. Lessons drafted earlier keep the fixture optional. `--check` now also
  fails a proposal whose `occurrences` exceeds its evidence blocks, and a fixture
  whose `before.excerpt` is not in the proposal's evidence. Rerun
  `learn_contract.py --check` on your queue after the bump.

### Added

- **Experience learning** (#81, phase 2b). `learn` takes a second source: the
  operator asks it to learn from a session, or `plan-validation`'s retro hands it
  the plan's signals. Signals are corrections, repeated failures, tool denials,
  reviewer findings and Doctor drift, each recorded as its own evidence block
  under `provenance-source` `session`, `denial`, `review` or `doctor`. The
  proposal format is 2a's, unchanged.
- **The `plan-validation` retro.** When a plan's last gate passes, after any
  reviewer pass, the retro lists the plan's signals, hands them to `learn` and
  records `**Retro:** <proposal ids>` or `no lessons` in the gate record. It
  never holds a gate.
- **Lesson-as-test.** Every lesson with a diff carries a
  `crew-lesson-fixture/1` fixture that replays the original failure.
  `learn_contract.py --eval-case <proposal> --out <dir>` renders a skill lesson
  and its fixture as a `claude plugin eval` plugin. Under the default
  with-without ablation, the no-plugin arm replays the failure and the plugin arm
  shows the fix. It renders only a lesson that writes a new skill; an edit to an
  existing skill is tested by hand, as docs/LEARNING.md describes, and a
  pre-lesson baseline arm is a follow-up. It reruns every gate first, writes
  only under `<dir>`, and runs nothing; an eval is billed, so the operator runs
  it.

### Changed

- `crew-lesson-fixture/1` is no longer provisional. Its shape is unchanged, and
  docs/LEARNING.md maps each field to a `claude plugin eval` grader.
- New `learn_contract.py --check` findings: `[classification]` when
  `occurrences` exceeds the evidence blocks; `[fixture]` when `before.excerpt`
  is not recorded evidence, when `expect.loads_skill` is not the skill the
  lesson writes, when it expects only `loads_skill` (not scored under the
  with-without ablation, so the test could not fail without the lesson), or
  when a 0.63.0+ lesson with a diff is `reviewed` or
  `promoted` without a fixture.
- The `reviewer` role checks that a lesson's fixture replays the recorded
  failure and would fail without the lesson.

## 0.62.0

### Consumer impact

- **Renamed or moved:** None.
- **Removed:** Crew's pi dispatch. The experimental pi extension
  (`pi-extension/index.ts`) and its `crew_agent` tool are gone, and with them
  the `CREW_PI_AGENT`, `CREW_PI_DISPATCH` and `CREW_AGENT_TIMEOUT_SECONDS`
  variables. The package no longer declares the `pi.subagents.agents` manifest
  entry or the `pi-subagents` peer dependency (nor the `@earendil-works/pi-coding-agent`
  and `typebox` peers the extension needed). No skill or role is removed.
- **Action needed:** pi users only. After the bump, pi registers no
  `crew.<role>` agents and no `crew_agent` tool; unset the `CREW_PI_*` and
  `CREW_AGENT_TIMEOUT_SECONDS` variables, which now do nothing. Crew still
  loads its skills on pi (package or `--skill`), and the roles stay readable in
  `pi-agents/*.md`. To run roles as workers on pi, use a supervising host such
  as operator; keep `npm:pi-subagents` only for your own agents.

### Removed

- **pi dispatch** (both paths). Crew on pi now provides skills and readable
  role files only; orchestration on pi belongs to a supervising host, not
  Crew. Removed: the `crew_agent` extension, its contract tests and fake-model
  fixtures, the `pi-extension` CI job, the `pi.extensions` and
  `pi.subagents` manifest entries, all peer dependencies, and the lead role's
  `crew_agent` dispatch sentence. The renderer still writes `pi-agents/*.md`
  in the same frontmatter dialect, so a host can load them.

### Changed

- `docs/quickstart-pi.md` is rewritten around install, skills-only use and
  readable roles, with an upgrade note; the plan to make `crew_agent` the
  default pi path is dropped. The README, `docs/MAINTAINERS.md` and the
  `doctor` skill no longer describe pi-subagents' tested range or the
  extension.

## 0.61.0

### Consumer impact

- **Renamed or moved:** None.
- **Removed:** None.
- **Action needed:** None. Onboarding apply keeps a project's existing
  `## Reporting contract` section and the audit still accepts the older one,
  so a project that wants decision keys and closing records edits its own
  `AGENTS.md` section by hand from `templates/AGENTS.md`.

### Changed

- **Decisions carry a key and close on a record** (crew#125). The reporting
  contract (every role, and `templates/AGENTS.md`) now lists each decision as
  `[key=<slug>] <question> — recommend <X>. If no reply: <default>.` A new
  rule, *A decision closes on a record*, keeps a decision open until a record
  carries its key, the human's words (or the evidence that made it moot) and
  the date; "later" is an answer with a date. The host rule now names
  decision records, so a supervising host's decision channel and record format
  still win.
- **`delta-handling`** gives an escalated delta a key and adds a
  `Decision record` line to the delta log, which holds the operator's words
  instead of only "Approved by the operator".
- **`plan-validation`** adds "The decisions were listed" to *What does NOT
  count as validation* and a promotion-checklist item: a phase is not complete
  while a decision it raised has no closing record.

## 0.60.0

### Consumer impact

- **Renamed or moved:** None.
- **Removed:** None.
- **Action needed:** None. A project that shadows `lead` or `reviewer`, or
  writes its own dispatch template, may want to adopt the split below.

### Changed

- **The dispatch packet keeps the ask apart from the spec** (crew#127).
  `orchestration-patterns` now splits a dispatch's task into the requester's
  ask, in their own words, self-contained and never widened into a coverage
  list, and the dispatcher's spec: build instructions, acceptance criteria
  and out-of-scope items. A reviewer judges against the ask, and the spec
  cannot add a requirement the ask lacks. `lead`, `reviewer`,
  `plan-execution` and the pi `crew_agent` tool's `task` parameter say the
  same where they restate the packet.

## 0.59.0

### Consumer impact

- **Renamed or moved:** None.
- **Removed:** None.
- **Action needed:** None.

### Added

- **Review rounds are bounded** (crew#126). `delta-handling` adds two rules.
  A review finding cannot amend the accepted ask: a fix that adds a guarantee,
  subsystem, compatibility surface or monitoring requirement the ask did not
  contain is scope expansion, whatever the finding's label. A new escalation
  class, repeated same-theme findings, escalates before another fix round
  when successive fixes keep accreting machinery around one questionable
  abstraction. Either escalation states the original requirement, the
  proposed expansion, the smallest compliant alternative, the consequences of
  each, and a recommendation. The reviewer role cites both rules and reports
  such findings in a new **Escalations** output section; the summary line
  states the escalation count without changing the verdict. Its adversarial
  posture is unchanged.

## 0.58.0

### Consumer impact

- **Renamed or moved:** None.
- **Removed:** None.
- **Action needed:** None.

### Added

- **Doctor reports the entry-file cost** (crew#129). A new
  `description-cost.entry-file` row, beside the description-budget row, sizes
  in characters the sections Onboarding merges from `templates/AGENTS.md`
  (about 19,400 chars at this version), names the largest, and adds them to the
  description total, so a consumer sees the full always-on cost. Pass
  `entry_file_cost(<crew root>)` to `compose_doctor_report` as `entry_file=`.
  It is reported, never failed; no rule changes, and the Work quality section
  stays always-on.

## 0.57.1

### Consumer impact

- **Renamed or moved:** None.
- **Removed:** None.
- **Action needed:** None.

### Added

- **Release notes say what moved** (crew#105). Each release section now opens
  with a fixed `### Consumer impact` section, described at the top of this
  file and in `docs/MAINTAINERS.md` (Versioning).
- **Skills-only on pi** (crew#105). `docs/quickstart-pi.md` section 7 shows
  how to load Crew's skills with `pi --skill`, without its roles or the
  pi-subagents peer. One `--skill <crew>/skills` loads every skill. This was
  verified on pi 0.87.1 and 1.4.0 against a fake model, with no billed calls.

## 0.57.0

### Added

- **Host switch for the pi extension.** `CREW_PI_DISPATCH=off` leaves the
  experimental `crew_agent` tool unregistered even when `CREW_PI_AGENT=1` is
  set, so a supervising host whose workers must not delegate can enforce that
  mechanically. The roles stay readable. Documented in `docs/quickstart-pi.md`
  section 6 and covered by contract tests for both states.

## 0.56.0

### Added

- **Experimental pi extension, opt-in** (crew#92). `pi-extension/index.ts`
  registers a `crew_agent { agent, task, cwd? }` tool. The tool runs a Crew role
  in its own pi process, built only on pi's extension API and CLI. It does
  nothing unless `CREW_PI_AGENT=1` is set, and it needs pi 1.4.0 or newer. Roles
  keep their subtractive posture (`--exclude-tools`) and reach the session's MCP
  servers, including pi's built-in MCP. Only `lead` can dispatch further, and
  depth is capped. Roles inherit the session's model and thinking level.
  Failures become tool errors, and output over 50 KB spills to a file. A project
  `.pi/agents/<role>.md` overlay applies only inside the session's own trusted
  project. A role inherits the session's project trust (`--approve`) only inside
  that project (symlinks resolved) when the session trusts it; otherwise it runs
  with `--no-approve`. Confirming an overlay grants no trust. See
  `docs/quickstart-pi.md` section 6.
- Contract tests for the extension (`tests/test_pi_extension.py`). They run the
  real pi CLI against a fake model and a fake MCP server, so they make no billed
  calls. A new `pi-extension` CI job runs them on pi 1.4.0.

### Changed

- Lead's dispatch guidance names `crew_agent` and bare role names when that tool
  is present. Otherwise it still dispatches `crew.<role>`.
- `package.json` declares the extension under `pi.extensions`, and declares the
  pi host packages `@earendil-works/pi-coding-agent` and `typebox` as `*` peers,
  as pi's package docs require.

### Fixed

- `docs/quickstart-pi.md` no longer says background roles reach MCP through
  ambient extensions without qualification. On pi 0.99 and newer, that holds only
  when pi-mcp-adapter is installed. pi-subagents does not connect pi's built-in
  MCP for Crew roles.

### Unchanged

- pi-subagents remains the default pi path, with the peer range
  `>=0.62.0 <0.82.0`. A later release is planned to drop `pi.subagents.agents`
  and the `pi-subagents` peer dependency.
