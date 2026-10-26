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
- **Action needed:** None. A project that shadows `lead` or `reviewer`, or
  writes its own dispatch template, may want to adopt the split below.

### Added

- **Doctor reports the entry-file cost** (crew#129). A new
  `description-cost.entry-file` row, beside the description-budget row, sizes
  in characters the sections Onboarding merges from `templates/AGENTS.md`
  (about 19,400 chars at this version), names the largest, and adds them to the
  description total, so a consumer sees the full always-on cost. Pass
  `entry_file_cost(<crew root>)` to `compose_doctor_report` as `entry_file=`.
  It is reported, never failed; no rule changes, and the Work quality section
  stays always-on.

### Changed

- **The dispatch packet keeps the ask apart from the spec** (crew#127).
  `orchestration-patterns` now splits a dispatch's task into the requester's
  ask, in their own words, self-contained and never widened into a coverage
  list, and the dispatcher's spec: build instructions, acceptance criteria
  and out-of-scope items. A reviewer judges against the ask, and the spec
  cannot add a requirement the ask lacks. `lead`, `reviewer` and
  `plan-execution` say the same where they restate the packet.

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
