# Quickstart — OpenAI Codex

Codex (CLI / IDE extension / cloud) reads `AGENTS.md` natively, loads the full skill catalog, reaches platform capabilities over MCP, **and dispatches subagents** — including from `AGENTS.md` instructions, which is what makes the routing table work here.

> **Corrected 2026-08-14.** This page previously called Codex a "solo harness with no subagent registry". That was wrong: Codex multi-agent stabilized in `rust-v0.145.0` (2026-07-21), before this foundation documented the harness. Subagent workflows are **enabled by default** and a project-scoped role registry exists.

## 1. The behavioral contract — already compatible

Codex reads the repo-root **`AGENTS.md`** natively (it originated the standard) — the same file Claude Code and pi.dev use, no shim required. Hierarchical `AGENTS.md` files in subdirectories also work. If the repo has no `AGENTS.md` yet, run onboarding from any harness (or copy `templates/AGENTS.md` and fill the ▸ blocks).

## 2. Install the skills

Codex loads portable `SKILL.md` skills from `.agents/skills/` (repo-level, scanned from cwd up to the repo root) and `~/.agents/skills/` (user-level). The foundation's frontmatter extras (`tier`, `requires`, `expects-local`) are ignored by Codex — the files load as-is.

> **Codex budgets its skills listing — unlike pi and Claude Code.** It renders a model-visible list of installed skills with their descriptions (that listing is how agents discover skills), and that list has a budget. Measured on `codex-cli` 0.150.1 against a real catalogue:
>
> | Entries | Section bytes | A 583-char description renders as |
> |---|---|---|
> | 7 | 3,512 | 583 — full |
> | 58 | 21,309 | **387 — truncated** |
> | 307 | 21,487 | 47 — a fragment |
>
> The cap is on **bytes (~21.5 KB)**, not on skill count, and **nothing was omitted** even at 307 entries — every skill stayed listed. So the failure mode is not a missing skill; it is *every* description degrading at once, which is worse, because the description is the entire discovery mechanism. Telemetry reports it (`omitted_skills`, `truncated_skill_descriptions`, `truncated_description_chars_per_skill`); the session shows no error.
>
> Practical consequences: this catalogue plus a consumer's own local skills already lands near the cap, so keep descriptions tight and front-load the discriminating words. If a skill seems ignored on Codex, suspect the budget before the files. `codex debug prompt-input` renders the model-visible prompt with no API call — the direct way to see what the model actually got.

**Install it as a plugin (recommended).** Codex reads `.claude-plugin/marketplace.json` directly — no `.codex-plugin/` needed, and no vendoring:

```sh
codex plugin marketplace add pixeloven/crew --ref v0.33.0
codex plugin add crew@crew
```

The `--ref` is a **marketplace** flag, not a `plugin add` flag; that is where the pin lives, and it is persisted in `config.toml`. Update by re-running `marketplace add` at a newer tag.

**Vendoring (teams that want the files committed):** copy `skills/` into `<repo>/.agents/skills/` and commit. This drifts from the foundation unless you re-copy, which is why the plugin path is preferred.

Your project's own local skills (the `expects-local` slot fillings) go in the repo's `.agents/skills/` either way; on a name collision the repo-level copy is the one closest to your working directory.

## 3. Grant the capabilities (MCP)

Codex speaks streamable-HTTP MCP with bearer auth — exactly the LiteLLM gateway's shape. In `~/.codex/config.toml` (or a trusted project's `.codex/config.toml`):

```toml
[mcp_servers.litellm]
url = "https://<your-litellm-host>/mcp"
bearer_token_env_var = "LITELLM_API_KEY"
```

Set `LITELLM_API_KEY` to the surface's **virtual key** — per the capability-parity pattern, a Codex surface is a new consumer: mint it its own VK with explicit `mcp_access_groups` (see the project's gateway-routing local skill); never reuse another surface's key. The VK decides which capabilities (KB, search, image gen, cluster reads, …) this Codex install can reach.

## 4. Verify

Start a Codex session in the repo and ask it to **"run the doctor"** — the `doctor` skill loads from the installed catalog and reports install state, reachable capabilities, and unfilled local-skill slots, closing with the onboarding profile. Then, if the repo isn't onboarded yet: **"onboard this project to harmony-crew"**.

## 5. Delegation — how the routing table works here

Codex delegates **when you ask directly, or when applicable `AGENTS.md` or skill instructions request it** ([docs](https://learn.chatgpt.com/docs/agent-configuration/subagents)). So the routing table in your `AGENTS.md` is the trigger — no extra wiring needed to get crew-style delegation on this harness.

Available to the model: `spawn_agent`, `wait_agent`, `send_message`, `list_agents`, `followup_task`, `interrupt_agent` — the last two give mid-run steer and stop, which not every harness offers. `/agent` inspects and switches between running agent threads.

**Named roles** live in `.codex/agents/*.toml` — project-scoped (`<project>/.codex/agents/`), user-scoped (`~/.codex/agents/`), or system-scoped — alongside built-in `default` / `worker` / `explorer`. Required keys are `name` (the **filename is not** the role name), `description`, and `developer_instructions`; the file also accepts the whole `config.toml` schema, but only a bounded allowlist is actually applied to the child session: `model`, `model_reasoning_effort`, `model_reasoning_summary`, `model_verbosity`, `personality`, `service_tier`, `[features]` and `skills.config` (the last two **only to disable** things). `sandbox_mode` and `mcp_servers` parse without error and are **silently ignored** — a role may reduce the parent session's authority, never replace it. (An earlier version of this page listed those two as working options. They don't.)

> **A plugin cannot ship Codex roles — this is a hard limit, not a backlog item.** Codex's plugin manifest has exactly four component slots: skills, MCP servers, apps, and hooks. Plugins are not a config layer, so nothing a plugin installs is ever scanned for an `agents/` directory. The seven crew roles therefore reach Claude Code and pi through the package and reach Codex not at all; on Codex the routing table in your `AGENTS.md` plus the loaded skills is the delegation mechanism, and `spawn_agent` targets the built-ins. If you want the named roles here, the consumer's own repo or `$CODEX_HOME` has to own the TOMLs — generating them from `roles/<role>/` into a consumer repo is a job for the `onboarding` skill, not for the plugin.

> **If you do write role TOMLs, leave `model` out.** Codex applies a role file's `model` and `model_reasoning_effort` *after* the `spawn_agent` arguments, so a pinned model in a role silently overrides the orchestrator's explicit choice — the opposite of every other harness, where the dispatcher wins. Omit both and the subagent inherits the parent session's model and effort.

*Verified against `openai/codex` source at commit `52e12e0` (2026-09-06), not against prose docs — `developers.openai.com` was unreachable from the verifying session. Re-check on a major Codex release; the applied-override allowlist has been tightened over time.*

> Use parallel agents for read-heavy work (exploration, tests, triage, summarization). Be careful with parallel *write*-heavy workflows — concurrent editors create conflicts and coordination overhead. Subagent workflows also consume more tokens than a single-agent run, since each subagent does its own model and tool work.

## What Codex doesn't get

- **Unattended updates** — `codex plugin marketplace add --ref` pins a tag, so updating is deliberate: re-run it at a newer tag. (This page previously said Codex has no plugin manager at all. That was true when written and is not now — `codex plugin marketplace` ships in 0.150.1, and it reads our existing `.claude-plugin/marketplace.json`.)
- **Cloud tasks are not a dispatch primitive.** Codex's parallel *cloud tasks* are independent agents the product runs for a human; every documented entry point is human-initiated. Don't build orchestration on them — `spawn_agent` is the agent-invocable path.
