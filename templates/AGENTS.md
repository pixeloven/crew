<!--
harmony-crew onboarding scaffold — the standard agent behavioral contract.

HOW TO USE
  1. Copy this file to your repo root as AGENTS.md.
  2. (Claude Code) add a one-line CLAUDE.md:  @AGENTS.md
     (pi.dev reads AGENTS.md directly from the repo root — no extra file.)
  3. Fill ONLY the blocks marked "▸ Fill for your project". Everything else is the
     portable behavioral spine the foundation provides — keep it as-is.

This is the merge-don't-replace seam: foundation behavior (the spine) + your project
specifics (the ▸ Fill blocks and your local skills). Keep this file BEHAVIORAL — facts,
conventions, and credentials live in SKILLS, never here.

Worked example (Harmony, the platform's first consumer):
  https://github.com/ductiletoaster/harmony/blob/main/AGENTS.md
-->

# AGENTS.md — Agent Behavioral Contract

This file drives **how agents behave** on this project: autonomy, delegation, routing, planning, memory, and how to apply shared platform skills to this repo's specifics. It is deliberately **behavioral, not factual** — conventions, infrastructure facts, and credentials live in **skills**, never here. Keeping this file behavioral is what lets it port across every project that consumes the platform.

> **One platform, many consumers.** The agent fleet and platform skills are shared (from the foundation); each consumer supplies its **own** local skills for its specifics. Nothing in the portable sections below is project-specific — your specifics live in the **▸ Fill** blocks and in your local skills. This `AGENTS.md` drives every harness that reads it — Claude Code, pi.dev, and OpenAI Codex — all of which can dispatch subagents.

---

## Autonomy & posture

Tool use is pre-approved (`defaultMode: dontAsk` in `.claude/settings.json` — a deliberate choice made during onboarding; see the Claude Code quickstart). **Act, then report** — never pause to ask before:

- **Loading skills and slash commands.** Load a skill proactively the moment the task touches its domain — a skill read is cheap; re-deriving conventions costs review cycles.
- **Calling MCP tools** — the platform's federated surface and connected services.
- **Running pre-approved CLIs**, including compound commands (pipes, `&&`, `;`, command substitution, env-var prefixes).
- **Dispatching subagents** per the routing rules below. Delegation is the default for multi-step work, not an escalation.

> **▸ Fill for your project:** your *ask list* — the genuinely destructive operations that should still prompt (e.g. `terraform destroy`, namespace deletion, force-push). Everything not on it: act, then report.

## Subagent delegation & routing

Delegate by work domain, without asking first. Reach for delegation by default on multi-step or multi-domain work; keep inline execution for single-file edits and quick lookups. Agents carry context via skills — you don't re-explain conventions to them.

> **Delegate on any harness that can.** Claude Code, pi.dev, and OpenAI Codex all support subagent dispatch — Codex acts on this table's instruction to delegate, so treat the table as a request, not a description. On a harness that genuinely cannot dispatch, apply the same skills **inline, solo**; the table still documents which discipline governs which kind of work.

| Task domain | Agent | Activation |
|-------------|-------|------------|
| Planning, orchestration, complex multi-step work | `lead` | dispatch |
| Write work — code, manifests, configs, PRs | `implementer` | dispatch |
| Pre-merge review, convention enforcement, seam detection | `reviewer` | dispatch |
| Pre-implementation option analysis, technology evaluation | `researcher` | dispatch |
| Issue / PR intake, labeling, routing | `triage` | **trigger** |
| Reactive diagnosis, health sweeps, incidents | `investigator` | **trigger** |
| Fast read + draft (answer a question / draft a reply) | `responder` | **trigger** |

**dispatch** = you invoke it from this session. **trigger** = it should run on an event or schedule with no human in the loop, which needs infrastructure you deploy — see `activation-contracts` and `templates/activation/`. A trigger-model role you haven't wired only runs when someone remembers it exists, and its work ends up absorbed into this session at a much higher cost.

### Quality gate (implementation work)

1. **Implement** — `implementer`
2. **Review** — `reviewer`
3. **Security** — `reviewer` with the `seam-detection` skill if the change touches secrets, auth, or external APIs
4. **Test** —
   > **▸ Fill for your project:** your verification commands (e.g. test runner, manifest/build validation, linter + formatter check).

### Isolation

Subagents write directly to the current working tree. Do **not** use `isolation: "worktree"` for in-repo implementation work — only for genuinely parallel independent branches.

## Planning model

Planning is conversational and agent-mediated, not document-driven. Plans are developed in **plan mode** with the operator; research is delegated to **`researcher`** (corpus-backed option analysis); designs are checked by seam audit and adversarial review (**`reviewer`**) before execution; durable design knowledge — decisions, architecture notes, phased plans — is persisted to the **knowledge corpus**, never to in-repo spec documents. Work items live in the tracker.

## Memory protocol

Follow **Pre-Task Recall** before starting and **Post-Session Persistence** after, per the the project's knowledge-capture local skill skill, with a `source_agent` set to your harness (or the dispatched agent's id). This is a platform capability — see *Fallback* for behavior when it's unavailable.

## Tools — the live catalogue is authoritative

What you can actually call is whatever your session lists right now, not what any document says. Search your available tools before concluding one doesn't exist — a tool you assumed away is indistinguishable, from the outside, from a tool that isn't there.

When a skill describes a tool that isn't in your session, or your session offers one no skill mentions, that gap is **reportable drift**, not a dead end: say what you found, use what you have, and let the mismatch be fixed rather than worked around silently.

## Interface boundaries (MCP vs CLI)

Pick the surface by *who the primary caller is*. **MCP tool** is canonical for agents mid-task (read paths, corpus writes). **CLI** is for humans/scripts/CI and for write operations the platform routes through it. When both exist, the CLI is a thin wrapper over the MCP/library path — no parallel implementation. Prefer CLI/MCP tools over hand-rolled API calls. See `agent-platform-design` for the full decision framework.

## Applying platform skills to local specifics

**Platform skills** (shared, from the foundation) teach *general patterns*. **This project's specific values and policies** live in **local skills** in `.claude/skills/`. When you apply a platform pattern, consult the matching local skill for this deployment's specifics. A consumer that isn't the platform's origin supplies its **own** equivalents of these local skills; the platform skills and this contract stay the same.

> **▸ Fill for your project:** a table mapping each kind of project-specific concern → the local skill that holds it. (Harmony's, for reference: infrastructure/access → `homelab-topology`; platform conventions → `harmony-platform-conventions`; secrets → the project's secret-paths local skill.)

## Tripwires — load the skill before the action

Most conventions are reference detail — load them as soon as the task touches their domain, per *Autonomy & posture*. A few are **silent landmines** — get them wrong and it fails with no obvious error. For these, load the named skill *before* the action, every time. The skill carries the detail; this is just the trigger.

> **▸ Fill for your project:** your silent landmines, each as *action → load this skill → one-line consequence*. (Harmony's, for reference: authoring a workload → `harmony-platform-conventions` → a missing control-plane toleration means the Pod never schedules, just `Pending`; editing an ExternalSecret → the project's secret-paths local skill → `refreshInterval:"0"` means a new key won't sync.)

## Fallback — when the platform is unavailable

The platform (corpus, LLM gateway, cluster) is the **default path — reach for it first**, and let an actual failed call, not an assumption, establish that something is unavailable. Once a capability is confirmed unreachable, degrade gracefully rather than fail — and say what you skipped:

- **No corpus / memory substrate** → work from the repo, git history, and the web; skip Pre-Task Recall and Post-Session persistence (note it).
- **No MCP gateway** → fall back to direct CLIs.
- **No cluster / live-infra access** → operate on the repo (code, manifests, plans); defer anything needing live infra and say so.

Every role keeps its core value on a bare repo — `reviewer` reviews the diff, `researcher` evaluates from web + repo, `implementer` edits code — and sharpens that with platform capabilities wherever they're reachable.

> **▸ Fill for your project:** any deployment-specific capabilities and their no-platform fallback (only if they differ from the above).

## Skills — how agents find them

Your harness lists every installed skill, with its description, before the first turn — foundation skills and this repo's own, together. **That listing is the discovery mechanism**, so there is no index to write or maintain here: put a skill where the harness looks and agents can find it. Load one the moment the work touches its domain; loading is cheap, re-deriving conventions is not. Where a local skill shares a name with a foundation one, the local copy wins.

The concern → local skill mapping under *Applying platform skills to local specifics* above is the only routing worth writing down, because it encodes a judgement the descriptions can't make for you. Don't restate the catalogue here — it goes stale the day someone adds a skill.

**Registration is what fails silently, not indexing.** A skill is discoverable only if it sits where that harness looks:

| Harness | Location |
|---|---|
| Claude Code | `.claude/skills/<name>.md` |
| pi.dev | `.pi/skills/<name>/SKILL.md` |
| Codex | `.agents/skills/<name>/SKILL.md` |

Miss one and that harness simply never sees the skill — no error, no warning. If you support more than one, single-source the file and symlink the others. Run `doctor` to compare what actually loaded against what's on disk.

Because discovery runs entirely on descriptions, a skill's `description` is its whole interface: say what it's for and when to reach for it, and front-load the discriminating words. A skill nothing matches against is a skill nobody loads.

## Git

- Use your harness's GitHub credential helper; never embed tokens in remote URLs.
- Commit format: `<type>(<scope>): <subject>` (feat, fix, docs, refactor, chore). Use `gh` for PRs, issues, releases.

> **▸ Fill for your project:** your remote URL and any repo-specific auth notes.
