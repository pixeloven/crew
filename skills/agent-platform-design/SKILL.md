---
name: agent-platform-design
description: Designing agent capabilities and surfaces — MCP vs CLI interface boundary decisions, skill vs agent tradeoffs, surface naming, and the operator-layer vs autonomous-runtime scope distinction. Load when designing new agent capabilities or evaluating platform options.
tier: concept
requires: []
---

## Two surfaces — keep them distinct

| Surface | Primary caller | Scope |
|---|---|---|
| **Scope 1 — operator layer** | Operators working ON the platform (interactive harness sessions) | Agents, skills, dispatch patterns in the harness config (e.g. `.claude/`) |
| **Scope 2 — autonomous runtime** | The project's in-cluster orchestrator running against external repos | Workflow engine, orchestrator, webhook dispatch (e.g. Harmony's Argo Workflows + Pydantic AI orchestrator) |

Requirements diverge between surfaces. Design decisions made for Scope 1 don't automatically apply to Scope 2. Establish clear surface naming conventions early so discussions don't conflate the two.

## Interface boundary: MCP vs CLI

For any new capability, decide the primary caller:

| Primary caller | Pattern |
|---|---|
| LLM mid-task (agents) | MCP tool first; optional CLI shim for human debug |
| Human at terminal / cron / CI | CLI command only; no MCP unless agents also need it |
| Both | MCP is canonical; CLI is a thin wrapper — no parallel implementation |

The MCP tool owns validation, schema, and side effects. The CLI forwards structured args and translates exit codes. Drift between surfaces is a bug.

### Off-the-shelf > custom — the strong default

Before designing a custom MCP server or wrapping a vendor in project code, check two things:

1. Does a maintained off-the-shelf option exist? (npm `pi-package` keyword, MCP server registries, vendor's own client SDK)
2. Is the vendor's own CLI / REST already shipping production-grade for this surface?

Case studies:
- **`@0xkobold/pi-mcp` over a `pi-mcp-adapter` fork** — the upstream maintainer's design (auto-connect at extension load, no `session_start` hook) worked under a session runtime where the maintained fork didn't. Swapping to the off-the-shelf adapter deleted hundreds of lines of code that would otherwise have needed ongoing maintenance.
- **Bundled `coder` CLI over an in-house `coder-mcp`** — Coder Inc. ships a tested, versioned CLI that already implements every workspace operation (start / stop / list / show / ssh-exec / logs / templates). The in-house wrapper shipped 5 tools, one of which (`run_in_workspace`) was a stub. Retiring the entire wrapper (~600 lines) in favor of the bundled CLI plus a skill that uses `bash` eliminated the maintenance surface.

**The cost of custom MCP wrappers**: every upstream release potentially breaks the translation layer, every SDK change can break lifecycle hooks, and the wrapper's tool surface is always a subset of what the upstream supports. The cost of skill + CLI: maintain one skill file.

**Use custom MCP only when**: (a) no upstream CLI/SDK exists, (b) agents need structured tool params that bash can't carry safely, or (c) the operation is so high-volume that the proxy + JSON-RPC overhead is a measurable bottleneck. Default no.

## MCP server provenance contract

If a tool is in the `tools/list` response, an agent will eventually try to call it. Stubs that return "not yet implemented" land at the model layer as a tool failure, which the LLM may treat as a transient error and retry — burning context window and operator trust.

Two rules for any MCP server a project ships or vendors:

1. **No stub tools.** If the operation isn't implemented end-to-end, remove it from `tools/list` (or prefix the description with `[UNAVAILABLE]` so the model can route around it). Failing fast on the boundary is better than mid-task surprise.
2. **Capabilities advertised in `initialize` must work.** If the server's `initialize` response advertises `resources`, then `resources/list` must return a well-shaped (possibly empty) array per the MCP spec — not "Method not found", not `{}` instead of `{"resources": []}`. The peer (LiteLLM, @0xkobold/pi-mcp, etc.) will call every advertised capability and pay a 30s timeout per broken one.

A capability that's *not* advertised in `initialize` is permitted to be absent. The contract is: don't advertise what you can't deliver.

## Skill vs agent tradeoff

Add a skill when: behavioral specialization is needed (how to do something) but the role and tool scope don't change.

Add an agent when: the role genuinely requires a different operational stance OR different tool access (e.g., Triage has no cluster access; Reviewer has no write access to code).

Most specialization resolves into a skill. New agents require justification.

## Harness capability claims carry a verification date

Any skill asserting what a harness can or cannot do is a **perishable claim**. Harnesses ship capabilities faster than documentation about them gets revisited: in one recent audit, three of four documented harnesses carried materially wrong capability claims, and one ("this harness has no subagent registry") was written twelve days *after* the feature it denied had stabilized.

Rules for capability claims:

- **Date them.** Write "verified <date> against <source URL>" next to the claim, so a reader knows how stale it is.
- **Prefer "verify at use" over hardcoded absolutes.** "Check whether your version exposes X" ages better than "X does not exist" — the same treatment the project's gateway-routing local skill gives version-sensitive gateway behavior.
- **Negative claims are the dangerous ones.** "The harness can't do X" makes agents stop looking. Before writing one, check the primary source; and when writing it, say what would falsify it.
- **Re-check on a cadence**, not only when something breaks. A capability that appeared silently produces no error — just a foundation quietly instructing agents not to use it.

## Prompt language: a skill is an instruction, not a description

Every skill file is loaded verbatim into an agent's context. Wording that merely *reads* as balanced documentation can behave as a suppressant — the model acts on what it retains, and negations retain well. the project's persona-tuning local skill states the same rule from the identity side: **add by example, not by prohibition.**

- **Lead with the action, not the absence.** "You carry no fixed skill list" primes against the very behaviour the sentence exists to produce. "Discover your skills through the index" produces it. Headings matter most — they're the scan-level unit.
- **Negative capability claims need a positive counterpart.** "The parent doesn't observe a worker mid-flight" is fine *next to* "so bound the work and steer with these primitives." Alone, it just tells the agent to stop trying.
- **Prefer "check, then use" over "probably unavailable."** A capability that might not be granted should be attempted and reported, not pre-emptively written off. Let a failed call establish absence.
- **Don't undersell a skill's own subject.** "The real gate is CI, not this" tells the agent its current path is second-rate; if both matter, say both matter.
- **Watch bolded prohibitions.** Bold survives compression into behaviour more than the qualifying sentence after it, so a bolded "Don't X" with a nuanced follow-up usually lands as a flat ban.
- **Budget, don't deter.** "Don't loop more than ~5 searches" reads as discouragement; "budget about five per question, and say why if you continue" reads as guidance.

**What this does not touch.** Safety and authorization gates, destructive-action warnings, accurate negative *facts*, and scope routing that names a better alternative are all correct as prohibitions — restricting an *action* is different from discouraging use of a *skill or capability*. When in doubt, ask which one a sentence restricts.

## Skill design guidelines

- Description carries trigger language and the load cue — for skills no agent always-loads, the description is the only load path, so name the tasks and phrases that should trigger it
- `tier`: `concept` (generic pattern) vs `subject` (about a specific tool/product)
- `requires`: the runtime capability the skill's guidance operates — `[]` (portable), `mcp:<group>`, `cluster`, or `external:github|web`; onboarding profiles and doctor checks filter on this
- Content: operational and prescriptive, not aspirational
- No `agents` field in frontmatter — agents load skills by explicit reference in their system prompts

## Platform tenets (durable bets)

Design new capabilities against the project's durable bets. Each consumer declares its own tenet list (in its local architecture skill or entry file); Harmony's, for example:
- Kubernetes as the delivery strategy
- Talos Linux / Sidero Omni on Proxmox as the substrate
- Agent-oriented platform direction (implementations reshape; direction holds)
- Python as the primary implementation language
- Open source first, permissive license preferred

Capabilities tied to transitional services (human-facing apps, specific AI frameworks) get lighter investment.

## Capability rollout sequence

1. Design the capability (this skill — option analysis, interface decision, skill/agent tradeoff)
2. Write the skill(s) encoding the pattern
3. Write or update the agent(s) that load the skill
4. Shadow mode: run and observe, no action taken
5. Draft mode: produce artifacts, human approves before publish
6. Autonomous: run and publish, human reviews asynchronously

Never skip the shadow and draft stages for capabilities that produce side effects.

## Knowledge corpus integration

Every significant capability should be documented in the vault:
- Design decisions → `kind: research` note
- Operational procedures → `kind: runbook` note
- Agent execution records → `kind: agent-run` note (automatic from orchestrator)

The vault is the institutional memory. Skills encode the how; vault notes encode the why and what happened.
