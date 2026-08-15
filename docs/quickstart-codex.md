# Quickstart — OpenAI Codex

Codex (CLI / IDE extension / cloud) reads `AGENTS.md` natively, loads the full skill catalog, reaches platform capabilities over MCP, **and dispatches subagents** — including from `AGENTS.md` instructions, which is what makes the routing table work here.

> **Corrected 2026-08-14.** This page previously called Codex a "solo harness with no subagent registry". That was wrong: Codex multi-agent stabilized in `rust-v0.145.0` (2026-07-21), before this foundation documented the harness. Subagent workflows are **enabled by default** and a project-scoped role registry exists.

## 1. The behavioral contract — already compatible

Codex reads the repo-root **`AGENTS.md`** natively (it originated the standard) — the same file Claude Code and pi.dev use, no shim required. Hierarchical `AGENTS.md` files in subdirectories also work. If the repo has no `AGENTS.md` yet, run onboarding from any harness (or copy `templates/AGENTS.md` and fill the ▸ blocks).

## 2. Install the skills

Codex loads portable `SKILL.md` skills from `.agents/skills/` (repo-level, scanned from cwd up to the repo root) and `~/.agents/skills/` (user-level). The foundation's frontmatter extras (`tier`, `requires`, `expects-local`) are ignored by Codex — the files load as-is.

> **Codex budgets its skills listing — unlike pi and Claude Code.** It renders a model-visible list of installed skills with their descriptions (that listing is how agents discover skills), but the list has a context budget. Over it, Codex **truncates descriptions and omits skills entirely**, reporting the loss only in telemetry (`omitted_skills`, `truncated_skill_descriptions`, `truncated_description_chars_per_skill`) — the session shows no error. Verified in `codex-cli` 0.147.0.
>
> Practical consequences: keep the installed catalogue tight rather than copying every skill you might one day want, front-load the discriminating words in each description, and if a skill seems to be ignored on Codex, suspect the budget before the files. `doctor`'s discovery check compares what actually loaded against what's on disk; Codex also exposes `skills.list` for an on-demand answer.

**User-level (recommended — no vendoring into the repo):**

```sh
git clone --depth 1 -b v0.13.0 https://github.com/ductiletoaster/harmony-crew /tmp/hc
mkdir -p ~/.agents/skills && cp -R /tmp/hc/skills/. ~/.agents/skills/
```

**Repo-level (teams that want skills pinned + committed):** copy into `<repo>/.agents/skills/` instead and commit. This vendors the catalog — pin the tag and re-run the copy to update, or the vendored copy drifts from the foundation.

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

**Named roles** live in project-scoped `.codex/agents/*.toml` (`name`, `description`, `developer_instructions`; optional `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, `skills.config`), alongside built-in `default` / `worker` / `explorer`. Generating the foundation's 8 crew roles into this format from the same `roles/<role>/` source is tracked in the foundation's tracker; until it ships, Codex delegates to its built-ins guided by your routing table and the loaded skills.

> Use parallel agents for read-heavy work (exploration, tests, triage, summarization). Be careful with parallel *write*-heavy workflows — concurrent editors create conflicts and coordination overhead. Subagent workflows also consume more tokens than a single-agent run, since each subagent does its own model and tool work.

## What Codex doesn't get

- **Auto-updates** — there is no plugin/package manager in the path; updating = re-running the step-2 copy at a newer tag.
- **Cloud tasks are not a dispatch primitive.** Codex's parallel *cloud tasks* are independent agents the product runs for a human; every documented entry point is human-initiated. Don't build orchestration on them — `spawn_agent` is the agent-invocable path.
