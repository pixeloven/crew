# Quickstart — OpenAI Codex

Codex reads the root `AGENTS.md`, loads Crew skills, and can dispatch its own
subagents when the behavioral contract requests delegation. Crew's plugin format
does not install named role files into Codex.

Codex multi-agent workflows and project-scoped role configuration were verified
against `openai/codex` source at commit `52e12e0` on 2026-09-06. Treat that as
dated compatibility evidence and re-check it on a major Codex release.

## 1. Install the skills as a plugin

Pin a published tag by replacing `vX.Y.Z`:

```sh
codex plugin marketplace add pixeloven/marketplace
codex plugin add crew@pixeloven
```

The marketplace is the catalogue repo; it pins each plugin by commit SHA,
so the served version is whatever `pixeloven/marketplace` currently points at. A resolved plugin normally appears at
`~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/skills`; the exact
skill-root table in `codex debug prompt-input "hi"` is stronger evidence.

### Enable packs per project

`codex plugin add` enables a plugin in `~/.codex/config.toml`, so it applies to
every project. Codex merges `plugins` across its config layers, so keep a pack to
the projects that use it: switch it off in `~/.codex/config.toml` and on in each
such project's `.codex/config.toml`:

```toml
# ~/.codex/config.toml
[plugins."infra-skills@pixeloven"]
enabled = false

# <project>/.codex/config.toml
[plugins."infra-skills@pixeloven"]
enabled = true
```

Codex reads a project's `.codex/config.toml` only when that project is trusted
(`projects."<abs>".trust_level = "trusted"`). Enabling a pack in your user config
alone is the alternative for a pack every project needs. Per-skill
`[[skills.config]]` entries are read from user config and `-c` flags, not from a
project's file. Checked against `openai/codex` `rust-v0.163.0` source on
2026-10-24.

Codex gives the skills list about 2% of the context window. When the list
outgrows it, Codex shortens every description, so packs a project doesn't use
still cost it.

Codex's legacy manifest path needs `.claude-plugin/plugin.json` to declare
`"skills": "./skills"`. Removing it installs zero plugin skills silently.

Vendoring `skills/` into `.agents/skills/` remains supported for teams that want
the files committed. Project-local skills also live there. Plugin entries are
namespaced as `crew:<name>` while project entries remain bare, so collisions
coexist and count as two runtime names.

## 2. Treat description pressure as measured, not constant

Codex budgets the model-visible catalogue, and Claude Code can also elide or
truncate descriptions under catalogue pressure. A skill may be exact, truncated,
loaded with no description, or omitted.

One dated observation — Codex CLI 0.150.1 on 2026-09-07, with 60 entries —
rendered a 22,216-byte skills-instruction block, shortened 33 descriptions, and
omitted none. This is evidence from that run, not a permanent platform byte
limit. Current telemetry may include `omitted_skills` and
`truncated_skill_descriptions`; inspect it rather than assuming one failure mode.

Crew's own CI limits descriptions to 300 characters and front-loads trigger
language. That policy reduces risk but does not promise that an arbitrarily large
consumer catalogue will never degrade.

## 3. Grant capabilities separately

Installation is independent of MCP grants. A typical streamable-HTTP grant is:

```toml
[mcp_servers.litellm]
url = "https://<your-litellm-host>/mcp"
bearer_token_env_var = "LITELLM_API_KEY"
```

The config proves a declared grant, not a working capability. Use a safe read-only
probe before reporting `working`; otherwise report `present`, `unavailable`, or
`not tested`.

## 4. Verify for free

From the consumer repository:

```sh
codex debug prompt-input "hi"
python3 /absolute/resolved/crew/root/scripts/check_skill_layout.py /absolute/consumer/repo
```

`codex debug prompt-input` is native introspection and makes no model call. Compare
disk and runtime names, roots, and descriptions in both directions. `codex exec`
is billed and requires explicit approval.

## 5. Delegation and onboarding

The `AGENTS.md` routing table triggers Codex's dispatch primitives. A project may
define its own `.codex/agents/*.toml`, but Crew neither renders nor installs those
files; audit them as project-owned configuration.

Leave `model` and `model_reasoning_effort` out of those project role files unless
the override is deliberate. In the dated source above, Codex applies role-file
values after dispatch arguments, so a pin can silently replace the dispatcher's
explicit choice. The parent session's authority remains the boundary: role-level
`sandbox_mode` and `mcp_servers` do not replace it. Cloud tasks are human-started
work, not an agent dispatch primitive.

Ask **“run Crew Doctor”** for the read-only health report. Ask **“onboard this
project”** for a non-mutating audit. Applying onboarding findings requires a
distinct explicit current-run authorization.
The supervising host verifies a fresh, non-persisted signal for that exact
invocation; saved, standing, reusable, and prior-run authority is rejected.
