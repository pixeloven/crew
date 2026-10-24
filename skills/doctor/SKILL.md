---
name: doctor
description: Use when asked to run Crew Doctor, verify installation or onboarding, debug missing roles/skills, or report what this session can reach. Separates installed, enabled, runtime-loaded, granted, degraded, and untested evidence.
tier: concept
requires: []
---

# Doctor

Crew Doctor is fully read-only. Never install, enable, update, delete, edit, or
restart anything while running it. Absence is evidence, not permission to repair.
Run free checks first and report only the current harness's runtime as runtime
truth; one harness cannot verify another.

## Evidence vocabulary

Keep these dimensions separate:

- **installation** — package/catalogue files exist at a declared install root;
- **enablement** — settings select that installation;
- **resolved runtime** — this harness actually loaded it in this session;
- **capability grant** — the session was given a tool or credential surface.

For observations use exactly: **present** (visible, not exercised), **working**
(a read-only probe succeeded), **unavailable** (absent or a probe proved unusable),
**not tested** (deliberately unprobed), **loaded-but-undiscoverable** (loaded but
its description is absent), **truncated**, and **omitted**. A config claim is
never `working`. Label every report item as **fact**, **inference**,
**recommendation**, or **untested** and retain the command/path that produced it.

## Probe cost and order

Run these free, read-only checks before considering inference calls:

1. inspect settings, manifests, registries, caches, and the session's supplied
   tool/skill/agent catalogues;
2. `claude plugin validate <absolute-crew-root> --strict` and
   `claude --plugin-dir <absolute-crew-root> plugin details crew`;
3. `codex debug prompt-input "hi"` for Codex's model-visible catalogue — this
   is native introspection and makes no model call;
4. the distributed validators under the resolved Crew package root.

`claude -p`, `pi -p`, `codex exec`, and equivalent prompt-mediated probes are
**billed**. Never run one without explicit approval for that probe. State what
the billed run would establish and leave it `not tested` when approval is absent.
A fresh session is sometimes the only runtime proof after an install change;
that does not make it free or implicitly authorized.

`scripts/crew_doctor.py` contains the fixture-tested evidence rules and probe
ledger. It starts no model processes. Locate it from the **resolved package
root**, never from the consumer's `scripts/` directory:

- Pi git package: the checkout containing `.claude-plugin/plugin.json`;
- Claude: the marketplace/cache `installLocation` or `installPath` root;
- Codex: the parent of the `/skills` root shown by `codex debug prompt-input`.

Run `python3 /absolute/resolved/crew/root/scripts/check_skill_layout.py
/absolute/consumer/repo`. Both paths must be absolute. This prevents a consumer's
same-named script from being invoked. If the installed root lacks the validator,
report that installed version as unable to perform the gate; do not fall back to
an incidental source clone.

## Checks

### 1. Reconcile installation, enablement, and version

**Pi.** In applicable project/user `.pi/settings.json`, find the current git
identity `git:github.com/pixeloven/crew@vX.Y.Z`. Report the configured pin and
the resolved checkout separately. Read the resolved version from that checkout's
`.claude-plugin/plugin.json`; never use `git describe`. A pin below `v0.35.0` is
**DEGRADED**, not missing: pi-subagents silently drops roles without frontmatter
`name:`, so the Crew fleet is invisible below the first role-discoverable
release. A configured `pi-subagents` pin below `0.62.0` is **DEGRADED** for
Crew `v0.39.0`+: it ignores the roles' `excludeTools`, so every role silently
gets `write` and `edit`. Also report duplicate project/user scopes and which scope the current
runtime actually resolved, if this Pi session exposes it.

**Claude Code.** Reconcile four distinct facts:

1. settings declare marketplace `pixeloven` (sourced from `pixeloven/marketplace`)
   and enable `crew@pixeloven`;
2. `known_marketplaces.json` records source, install location, and timestamp —
   it does **not** carry a served version;
3. the marketplace clone's `.claude-plugin/plugin.json` carries the served
   version;
4. `installed_plugins.json` records installed paths/versions/scopes. Enumerate
   every `plugins["crew@pixeloven"][]` record and flag stale or duplicate scopes.

Only this Claude session's catalogue can prove its loaded version. Registry
agreement is installation evidence, not runtime proof.

**Codex.** Check the marketplace pin and `plugins."crew@pixeloven".enabled` in
`config.toml`, then inspect
`~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills` and the exact
skill-root paths from free `codex debug prompt-input`. A repo/user
`.agents/skills/` copy remains a supported vendored alternative. Report every
root and version; duplicate/stale roots are findings. An absent `mcp_servers`
entry belongs only to the capability-grant check below, never installation.

After all three, report cross-harness version skew as an observed comparison,
without claiming that any one harness loaded another harness's files.

### 2. Validate entry files without judging by size

Confirm the repo-root `AGENTS.md`; Claude projects normally have a `CLAUDE.md`
importing it. Audit behavior, filled placeholders, delegation, tripwires,
delivery contracts, and runbook pointers. Facts may merit an Onboarding
recommendation, but a mature or long file is not inherently degraded.

The reporting contract is a required spine section, however mature the file.
Check it with the read-only helper from the resolved package root:
`python3 /absolute/resolved/crew/root/scripts/onboarding_contract.py
--check-reporting /absolute/consumer/repo/AGENTS.md`. A missing section is
**MISSING** and a section without its decisions-first rule is **DEGRADED**; both
are drift for Onboarding to merge, never for Doctor to repair. When the session's
host reserves `AGENTS.md` for humans, add `--audit-profile hosted`: the result
is **N/A**, because the host's task contract supplies reporting.

### 3. Separate capability declarations from working probes

Derive foundation requirements from installed `requires:` frontmatter and local
requirements from the consumer overlay. A listed tool/grant is `present`; call
only safe read-only probes and promote it to `working` on success. A failed probe
is `unavailable`; an intentionally skipped or billed probe is `not tested`.
Inspecting an MCP config proves configuration only. Record shell/CLI fallback as
a separate capability, not MCP parity.

### 4. Derive local slots and profile

Union the installed catalogue's actual `expects-local:` declarations. Today the
declared set is `platform-conventions`, `topology`, `protected-seams`,
`secret-paths`, `agent-runtime`, and `decision-record-format`; derive rather than hard-code it in a report.
`litellm-access-map` and `vault-ops` are recommended vocabulary, not declared
slots, and must never appear as unfilled unless a future installed skill actually
declares them.

Pass the other installed plugin and package roots found in check 1 to
`inspect_packs`. A root is a pack when a skill declares `plugin:crew@>=X` or
`provides:`. Then pass the packs to `declared_local_slots(..., packs=...)`: each
pack's `slots.txt` adds its own slots to the declared set, labelled with the
pack, and an unfilled one is reported as that pack's slot. A slot name two packs
declare, or a pack declares over a Crew slot, is `DEGRADED`; never pick an owner.

Then report who fills each declared slot. A local overlay skill fills a slot by
`provides:` or by the `<project>-<slot>` naming convention; a pack skill fills one
only by `provides:`, including a slot another pack declares. Report "slot X
filled by pack Y" alongside local fills. **A local overlay outranks a pack.** On
Claude and Codex both copies
load, so name both. A local fill that still carries `▸ Fill` is `DEGRADED`
(partial): name its unfilled section headings and point at onboarding (Thorough). Verify every pack's `plugin:crew@>=X` against the resolved
Crew manifest; an unmet minimum is `DEGRADED`.

Then check for skills that moved out of Crew. `moved_skill_references` scans the
consumer's `AGENTS.md`, `CLAUDE.md`, local skills, and role overlays for any name
in the `MOVED_SKILLS` table, bare or `crew:`-prefixed; pass its result with the
detected packs to `compose_doctor_report`. A referenced skill whose pack is not
detected is `DEGRADED` — name the pack to install. With the pack installed, a
lingering `crew:<skill>` is still `DEGRADED` until it becomes `<pack>:<skill>`.
Report only; the rename is Onboarding's to propose.

Report the always-on description total for Crew plus every detected pack against
the dated harness budgets in `crew_doctor.py`, which are measurements and not
limits. This row never fails. When the total exceeds a budget, name the packs an
operator could disable for headroom.

Emit exactly one profile using this shared taxonomy:

- `personas` when repository evidence declares an OpenClaw/persona runtime;
- otherwise `platform` when at least one project capability is **working**;
- otherwise `portable`.

Persona evidence takes precedence; list working platform capabilities separately.
Onboarding consumes this exact value and rule.

### 5. Validate role files and effective posture

Validate package roles plus consumer `agents/*.md`, `.claude/agents/**/*.md`, and
`.pi/agents/**/*.md` with the absolute package-root layout validator. Require YAML
frontmatter `name` and `description`. Neutral and Pi role names must match their
filenames; a Claude consumer role's frontmatter `name` owns its resolved identity
and may differ from its filename. Claude role names use lowercase letters and
hyphens. Reject missing, malformed, or duplicate resolved identities. A Pi
overlay shadows a Crew role only when it declares `package: crew` with the same
name (identity `crew.<role>`); report a bare-named one as a separate agent, and a
bare `reviewer` or `researcher` as overriding the pi-subagents built-in. A missing
Pi name is a silent-drop finding. Reject `model`, `thinking`,
`effort`, `model_reasoning_effort`, `turnBudget`, and `maxTurns`: dispatch owns them.

Report every resolved role's effective tools, not only its declared posture.
`drafts` on Claude denies surgical `Edit`/`NotebookEdit` but retains `Write`, so
it can create **and overwrite** files. All shipped roles retain shell access;
therefore frontmatter write restrictions are advisory unless the host sandbox or
permission system enforces them.

Package-role runtime expectations are harness-specific: Claude and Pi should
resolve the seven rendered roles; Codex plugins do not carry them, so confirm the
project's routing contract and available Codex dispatch primitives instead.

### 6. Check intake and collisions

If Triage is routed, read the repository's label taxonomy and verify it through
the configured GitHub interface. Do not create labels. For collisions, Pi's flat
namespace lets the nearest project entry win; Claude and Codex namespace plugin
skills (`crew:name`) so plugin and bare project entries coexist. Name both copies,
their roots, and whether the local copy appears stale. Counts are per resolved
runtime name, so a namespaced collision counts as two.

### 7. Compare disk and runtime in both directions

Enumerate directory-form skill files in the resolved foundation root and local
overlay. Compare them with **this harness's** model-visible catalogue. Report:

- disk-only entries as `omitted` when a runtime catalogue was captured, or `not
  tested` when none was;
- runtime-only entries as `present` from another root and identify that root;
- entries with absent descriptions as `loaded-but-undiscoverable`;
- shortened descriptions as `truncated`;
- exact, usable entries as `working`.

Both Codex and Claude can degrade catalogues under pressure. Codex may report
`omitted_skills` and `truncated_skill_descriptions`; observed totals are dated
measurements, not permanent byte limits. Pi runtime discovery must come from Pi;
if unavailable, say `not tested`. A matching count is insufficient: pass only
when names, backing roots, and full descriptions match after applying the
harness's namespace rules.

### 8. Compare the capability map with this machine

Run the read-only inventory engine from the resolved package root:
`python3 /absolute/resolved/crew/root/scripts/crew_inventory.py --project
/absolute/consumer/repo --format json`. Pipe what only this session can see
with `--observations -`: the MCP servers and tool names visible to you, in the
capture shape (`schema_version: 1`, `harness`, `captured_at`,
`source_command`). Never run `claude mcp list` or `codex mcp list` to get
them. An observation can raise a provider to `present`, never to `working`.

Pass the result to `compose_doctor_report` as `inventory=`. The
`inventory.capability-map` row compares the `## Capabilities` table in the
`agent-runtime` slot with this machine:

- **OK** when the digest in its markers matches;
- **DEGRADED** when it differs on this machine, naming the changed rows. A
  committed map can describe a teammate's machine, so recommend onboarding
  and let the operator decide;
- **MISSING** when there are no markers, or only the template's empty ones.

Report only. Writing the map is Onboarding's job.

### 9. Check the proposal queue and learned skills

Read the consumer's declared `proposal-queue:` and learned skills with
`learn_contract.inspect_proposals(<consumer-root>, tool_versions=...)` (or
`python3 /absolute/resolved/crew/root/scripts/learn_contract.py --inspect
<consumer-root> --tool-version gh=X.Y.Z`), and pass the result to
`compose_doctor_report(proposals=...)`. Supply only versions this session
observed, such as a `gh --version` you already ran; an unsupplied version stays
untested. The rows follow docs/LEARNING.md:

- `proposals.queue` — `N/A` when nothing is declared (learn is report-only);
  `DEGRADED` when the queue sits in a skill root or holds a malformed proposal.
- `proposals.staleness` — `DEGRADED` when an open proposal's target hash or tool
  version moved since drafting.
- `learned.skills` — `DEGRADED` when a learned skill's marker version differs
  from the current tool; name its `promoted-in` commit to roll back.

There is no age threshold. Report only: promotion and rollback are the operator's.

## Report contract

Produce one row per check:

`check | status (OK / MISSING / DEGRADED / N/A) | fact | inference | recommendation | untested | repeatable evidence`

Then include:

- **Profile:** one of `portable`, `platform`, `personas`, using the rule above;
- **Top action:** exactly one highest-leverage next action, or `healthy — nothing
  to do`.

Never turn an untested state into an assertion. Keep Doctor read-only even when
the next action is obvious.
