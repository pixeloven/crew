# Quickstart — pi.dev

## 1. Install a role-discoverable release

Pin a published Crew release for reproducibility; replace `vX.Y.Z` with the
chosen tag:

```json
{
  "packages": [
    "npm:pi-subagents@0.81.0",
    "git:github.com/pixeloven/crew@vX.Y.Z"
  ]
}
```

Crew must be `v0.35.0` or newer. Earlier rendered Pi roles omitted frontmatter
`name:`; pi-subagents silently drops such files. Read the configured pin from
settings and the resolved version from the checkout's
`.claude-plugin/plugin.json`. Do not use `git describe` for package version.

Crew `v0.39.0` and newer require `pi-subagents` `>=0.62.0`. The roles express
their write posture with `excludeTools`, which older pi-subagents ignores, so
every role would silently receive pi's full default tool set, `write` and `edit`
included. Crew declares the tested range `>=0.62.0 <0.82.0` as its peer
dependency; `0.81.0` is the newest release verified to discover every role as
`crew.<role>` with its `excludeTools`. Treat a newer minor as untested until
Crew widens the range.

### Enable packs per project

Add each pack to the `packages` of the project that uses it, in `.pi/settings.json`
(`pi install git:github.com/pixeloven/<pack>@vX.Y.Z -l`), rather than to
`~/.pi/agent/settings.json`. User settings are the alternative for a pack every
project needs. Pi lists every visible skill's description in full in every
session, with no budget, so each pack a project doesn't use is pure cost there.
A package's `skills` filter (`"!skills/<name>"`) narrows one pack further.

## 2. Verify runtime discovery

In the intended Pi runtime, run its native `/subagents-doctor`. It should list
the seven Crew roles under their package-qualified names (`crew.lead`,
`crew.triage`, `crew.investigator`, `crew.researcher`, `crew.responder`,
`crew.reviewer`, `crew.implementer`) and the package skill tree. Package skill and role
discovery are separate; report which half failed.

If skills appear but roles do not, inspect both the package's
`pi.subagents.agents` manifest entry and each role's `name:` frontmatter. These
are separate, historically observed silent-failure seams.

Do not substitute another harness's result for Pi runtime evidence. `pi -p` or
any prompt-mediated fresh-session probe is billed and requires explicit approval.

## 3. Dispatch the qualified name

Every Crew role declares `package: crew`, so pi-subagents registers it as
`crew.<role>`; `name:` stays the bare local name. Dispatch `crew.reviewer`, not
`reviewer`. A bare `reviewer` or `researcher` resolves to pi-subagents' own
built-in agents. That is intended: pi-subagents' acceptance review and profiles
dispatch those bare names, and Crew no longer silently replaces them. The other
five bare names currently fall back to the unique local name (bare `lead`
reaches `crew.lead`), but that breaks as soon as any other source adds a
same-named agent, so dispatch the qualified name for every role.

To shadow a Crew role from a project overlay, the `.pi/agents/<role>.md` file
must also declare `package: crew`. Without it, the file registers as a separate
bare-named agent and the packaged `crew.<role>` stays in effect.

## 4. Project behavior and overlay

Pi reads the repo-root `AGENTS.md`. Canonical project skills live in
`.agents/skills/<name>/SKILL.md`; project roles live in `.pi/agents/<name>.md`.
Pi's skill namespace is flat and walks project scope before packages, so a local
same-named skill wins. Doctor reports the collision and both roots.

Run the installed validator by absolute Crew package path:

```sh
python3 /absolute/resolved/crew/root/scripts/check_skill_layout.py /absolute/consumer/repo
```

It catches missing role identity/description and forbidden runtime knobs as well
as invisible skill layouts.

## 5. Role posture and onboarding

Pi roles subtract from pi's default tool set rather than allowlisting:
`writes: none` renders `excludeTools: write, edit`, `writes: drafts` renders
`excludeTools: edit`, and `writes: full` excludes nothing. No role declares
`tools:`, because pi's `tools:` is a strict allowlist that would also shut out
ambient extensions. `lead` gets nested dispatch through
`allowNestedSubagents: true`. Every role retains `bash`, so file posture is
advisory unless the host permission system or sandbox enforces it. Dispatch
configuration owns model, reasoning depth, and turn budget.

Through pi-subagents, Crew roles reach MCP less than the operator session
does. A foreground child never loads ambient extensions. A background (`async`)
child loads them, so it reaches MCP only when the MCP comes from an extension,
such as pi-mcp-adapter's proxy tool. Pi's built-in MCP (pi 0.99 and newer) is
not an ambient extension: pi-subagents connects it only for a role whose
frontmatter lists `mcp:` entries, and no Crew role does. So without
pi-mcp-adapter installed, Crew roles reach no MCP server in either mode. The
experimental `crew_agent` tool (section 6) closes this gap. On every harness the
write posture limits dedicated file-write tools only: MCP side effects are
governed by the role's behaviour, not by `writes:`.

Ask **“onboard this project”** for a read-only audit. Applying findings requires a
separate explicit current-run authorization.
The supervising host verifies a fresh, non-persisted signal for that exact
invocation; saved, standing, reusable, and prior-run authority is rejected.

## 6. Experimental: Crew's own `crew_agent` tool

Since 0.56.0, Crew ships its own minimal agent extension for pi,
`pi-extension/index.ts`. It is **experimental and off by default**: without the
opt-in it registers nothing, and the pi-subagents path above is unchanged and
remains the default. Turn it on for a pi process with an environment variable:

```sh
CREW_PI_AGENT=1 pi
```

A supervising host whose workers must not delegate can switch the tool off
regardless of the opt-in. With `CREW_PI_DISPATCH=off` in the environment the
extension registers no `crew_agent` tool, in the session or in any role it would
have started. The roles stay readable: the rendered `pi-agents/*.md` files and the
pi-subagents path are untouched. Any other value leaves the opt-in in charge.

The extension registers one tool, `crew_agent { agent, task, cwd? }`. It runs a
Crew role in a separate `pi` process and returns the role's final answer as the
tool result. Use bare role names (`reviewer`, not `crew.reviewer`): the tool is
Crew's own, so a name can only mean a Crew role. To run several roles in
parallel, make several calls in one turn. The tool is built only on pi's own
extension API and CLI:

- **Posture.** The role's `excludeTools` is passed to `pi --exclude-tools`, so it
  subtracts from pi's defaults exactly as section 5 describes. pi-subagents'
  tools (`subagent`, `subagent_supervisor`, `bg_wait`, `contact_supervisor`) are
  always excluded too, so posture is the same whether pi-subagents is installed
  or not.
- **MCP.** Each role runs as an ordinary pi process, so it connects the same
  `mcp.json` servers and loads the same extensions as your session. This
  includes pi's built-in MCP.
- **Nesting.** Only `lead` (`allowNestedSubagents: true`) keeps `crew_agent`.
  The depth is capped: a role that `lead` dispatches cannot dispatch further.
- **Model.** A role inherits your session's model and thinking level.
- **Result.** A failed role (non-zero exit, a model error, an abort) is a tool
  error. Output over 50 KB is cut off, and the full text is written to a file
  whose path appears in the result. Aborting your turn stops the role. Set
  `CREW_AGENT_TIMEOUT_SECONDS` to stop roles that run too long; by default there
  is no timeout.
- **Overlays.** A project `.pi/agents/<role>.md` that declares `package: crew`
  replaces the packaged role, the same rule as section 3. It is used only when
  pi trusts the project. In an untrusted project, the interactive UI asks first.
  Without a UI, the packaged role runs and the result says the overlay was not
  used. Only overlays inside the session's project count: the search does not
  go above the project directory, and an overlay under a `cwd` outside the
  project is never used (the result says the packaged role ran).
- **Trust.** A role gets your session's project trust only when it runs
  inside the session's project and your session trusts that project. Paths are
  compared after resolving symlinks, so a `cwd` that links out of the project
  counts as outside it. Confirming an overlay in the UI only lets that role
  prompt run; it grants no trust. A trusted role starts with `--approve` and
  loads the same trust-protected project resources (`.pi/settings.json`,
  project extensions, `.pi/mcp.json`) as your session. Otherwise it starts with
  `--no-approve`, so a role never gains trust your session lacks. A `lead`
  passes the same rule on to the workers it dispatches.

It needs pi 1.4.0 or newer (the oldest version tested). On an older pi it does
not load and shows a warning. It works alongside pi-subagents: both tools are
registered, and neither shadows the other. Each dispatch starts a new pi process
and reconnects stdio MCP servers, so it starts more slowly than an in-process
pi-subagents child. Not yet verified: real models (the tests use a fake one),
Windows, and pi-mcp-adapter.

This release ships both paths. A later release is planned to make `crew_agent`
the pi path and drop the `pi.subagents.agents` manifest entry and the
`pi-subagents` peer dependency. pi-subagents then stays available for your own
agents.
