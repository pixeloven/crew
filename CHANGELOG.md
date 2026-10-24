# Changelog

Release notes for each version, newest first. Every version bump adds its
section here in the same PR. Earlier releases are described in their pull
requests and tags.

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
  project. See
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
