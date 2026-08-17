---
name: agent-platform-design
description: Designing agent capabilities and surfaces — the three interface classes (MCP, AXI, CLI) and which one a capability belongs in, skill vs agent tradeoffs, surface naming, and the operator-layer vs autonomous-runtime scope distinction. Load when designing a new agent capability, deciding whether a tool federates through the gateway or stays local to one machine, or evaluating platform options.
tier: concept
requires: []
---

## Two surfaces — keep them distinct

| Surface | Primary caller | Scope |
|---|---|---|
| **Scope 1 — operator layer** | Operators working ON the platform (interactive harness sessions) | Agents, skills, dispatch patterns in the harness config (e.g. `.claude/`) |
| **Scope 2 — autonomous runtime** | The project's in-cluster orchestrator running against external repos | Workflow engine, orchestrator, webhook dispatch (e.g. Harmony's Argo Workflows + Pydantic AI orchestrator) |

Requirements diverge between surfaces. Design decisions made for Scope 1 don't automatically apply to Scope 2. Establish clear surface naming conventions early so discussions don't conflate the two.

## Interface boundary: three classes — MCP, AXI, CLI

For any new capability, two answers pick the class: **who calls it**, and **whose credentials it carries**. Capability never picks it — the same capability legitimately exists in more than one class.

| Class | Primary caller | Authorization | Where it runs |
|---|---|---|---|
| **MCP** | An LLM mid-task, across every consumer | **Federated** — the gateway is the authorization boundary; tools are virtual-key-scoped and shared | Anywhere the gateway reaches: cluster services, vendor APIs |
| **AXI** | An agent, on the machine it is already running on | **None of its own** — it inherits that machine's credentials and the invoking user's identity | Local: a workstation, a worker's own sandbox |
| **CLI** | Humans, scripts, CI | Whatever the shell already holds | Terminals, pipelines, runbooks |

**AXI** — *Agent eXperience Interface* — is a CLI built for an agent to invoke over shell execution rather than for a human to read: token-efficient structured output, minimal default schemas, definitive empty states, structured errors with meaningful exit codes, no interactive prompts, and next-step suggestions in the output. It is a published 10-principle standard; read it before building or reviewing one. Nothing stops a human from running an AXI — the class describes who it is *designed* for, not who is allowed.

### Authorization decides it

A tool placed behind the gateway is reachable by **every** consumer whose key carries its access group. That is the point: one place to grant, one place to revoke, one place to budget and audit. It is also precisely why a personal workplace credential must not go there — federating a mailbox, a chat account, or a calendar OAuth token turns one person's private surface into a capability every holder of that key inherits, and the gateway cannot narrow it back down to the human it belongs to.

An AXI has **no auth story, deliberately.** It runs as you, on your machine, against credentials that never leave it. Treat that as a property to use rather than a hole to plug: it is what makes AXI the right class for workplace credentials — chat, mail, calendar OAuth — where the blast radius should stay the machine that already holds the credential.

So:

- The credential must be **shared, centrally granted and revocable** → **MCP**.
- The credential is **personal to one machine or one human** and must never leave it → **AXI**.
- The caller is a **human, a script, or CI** → **CLI**.

When agents and humans need the same *shared* capability, MCP stays canonical and the CLI is a thin wrapper over it — no parallel implementation, and drift between the two is a bug. The MCP tool owns validation, schema, and side effects; the CLI forwards structured args and translates exit codes.

### Failure modes of choosing wrong

- **MCP for a personal credential.** The credential becomes a shared capability. Every consumer holding that access group can read the mailbox or post as the account, and revocation is all-or-nothing.
- **MCP for something only one machine needs.** Tool schemas are resident in every consumer's context window whether or not the tool is ever called, and tool-list budgets are finite — a niche tool crowds out ones agents actually use.
- **AXI for something several consumers need.** N installs, N credential copies, no central revocation, no shared budget or audit trail — and an in-cluster agent with no workstation cannot reach it at all.
- **CLI (human-shaped) for an agent caller.** Help text where the agent expected data, prose errors on a stream it doesn't read, prompts that hang an unattended run, ambiguous empty output it re-runs to confirm. It works — and it spends turns on every single call.

### The measured cost

The AXI standard publishes benchmark data covering all three classes over one task set. Browser automation, **490 runs** (14 tasks × 7 conditions × 5 repeats), Claude Sonnet 4.6:

| Class | Condition measured | Cost/task | Input tokens/task | Success | Turns |
|---|---|---|---|---|---|
| **AXI** | `chrome-devtools-axi` | **$0.074** | **~79K** | 100% | 4.5 |
| **CLI** (raw baseline) | `agent-browser` | $0.088 | ~93K | 99% | 4.8 |
| **MCP** | `chrome-devtools-mcp` | $0.100 | **~185K** | 99% | 6.2 |

MCP's overhead is mechanical rather than incidental: tool schemas sit resident in context — the same run attributes **~28.5% of input tokens** to them — so the cost is paid every turn whether or not a tool is called, and it compounds across multi-step tasks. That is the ~2.3× token gap between the AXI and MCP arms. A second benchmark in the same repository (GitHub operations, 425 runs) orders the three classes identically.

Read the numbers as an order-of-magnitude signal rather than a neutral result — they are the standard author's own published runs, and the AXI arm is the one being advocated. The *mechanism* is checkable independently of whose benchmark measured it, and it is the part that should drive design.

Sources, verified 2026-08-17 against `kunchenguid/axi@408a6536625e5b05e5c56e6c4a04fe83e1f510a5` (2026-08-16): summary table in `README.md`; per-condition figures and the schema-overhead limitation in `bench-browser/published-results/report.md` (which reports the MCP arm at $0.1005 — the README summary rounds it to $0.101); the 10 principles in `.agents/skills/axi/SKILL.md`. Published as the `axi.md` site (`docs/index.html` in that repo).

### Worked example: both classes stay

Browser automation is the case where one capability correctly lives in two classes at once:

- **`chrome-devtools-axi`** — local workstation browsing. Runs against the browser on the machine the agent is already working on, using whatever that browser is logged into. No key, no gateway, no shared state.
- **A federated browser MCP** — a shared headless browser (e.g. browserless behind a Playwright-MCP server) exposed as a virtual-key-scoped access group. Every consumer holding the group gets it, including agents running in-cluster with no workstation to borrow.

**Both stay.** They are not redundant and the newer one does not supersede the other; the chooser is the caller. An agent on a workstation reaches for the AXI. An agent in the cluster — or any consumer that has to be centrally granted and revoked — reaches for the MCP. Consolidating them would either strand the in-cluster agents or push a personal browser session behind a shared key.

The general form: a capability being available in one class is not an argument for removing it from another. Ask which caller each one serves before proposing consolidation.

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

- **Lead with the action, not the absence.** "You carry no fixed skill list" primes against the very behaviour the sentence exists to produce. "When the work touches a skill's domain, load it" produces it. Headings matter most — they're the scan-level unit.
- **Negative capability claims need a positive counterpart.** "The parent doesn't observe a worker mid-flight" is fine *next to* "so bound the work and steer with these primitives." Alone, it just tells the agent to stop trying.
- **Prefer "check, then use" over "probably unavailable."** A capability that might not be granted should be attempted and reported, not pre-emptively written off. Let a failed call establish absence.
- **Don't undersell a skill's own subject.** "The real gate is CI, not this" tells the agent its current path is second-rate; if both matter, say both matter.
- **Watch bolded prohibitions.** Bold survives compression into behaviour more than the qualifying sentence after it, so a bolded "Don't X" with a nuanced follow-up usually lands as a flat ban.
- **Budget, don't deter.** "Don't loop more than ~5 searches" reads as discouragement; "budget about five per question, and say why if you continue" reads as guidance.

**What this does not touch.** Safety and authorization gates, destructive-action warnings, accurate negative *facts*, and scope routing that names a better alternative are all correct as prohibitions — restricting an *action* is different from discouraging use of a *skill or capability*. When in doubt, ask which one a sentence restricts.

## Skills that describe code are a second source of truth

A skill documenting how code behaves — a label format, an exit-code contract, a parser's quirk — becomes wrong the moment that code changes, and nothing links the two. The failure is silent: the skill still reads plausibly, and an agent follows it into behaviour the code no longer has.

- **Cite `file:line` for any claim about code**, so a reader can check it in one step rather than trusting it.
- **Re-validate when the cited source changes.** A diff touching a file a skill cites is a prompt to re-read the skill, and worth calling out in review.
- **Prefer describing the contract over the implementation.** "Exit codes distinguish transient from structural failure" survives a refactor; "exit 75 means retry" does not.
- **When in doubt, point rather than copy.** A skill that says where the truth lives ages better than one that restates it.

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
