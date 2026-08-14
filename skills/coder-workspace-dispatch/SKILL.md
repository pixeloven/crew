---
name: coder-workspace-dispatch
description: Dispatch and operate Coder dev workspaces (sandboxes) from an agent session — via the federated `coder` MCP tools (any client whose VK holds the `coder` access group) or the bundled `coder` CLI (pi). Use when a task needs to run a project's real app stack (Docker compose, full boot, browser-reachable UI) that can't run inside the agent's local sandbox, or to demonstrate work in a browser.
tier: subject
requires: [mcp:coder]
audience: [crew]
expects-local: [litellm-access-map, platform-conventions]
---

## When to use

Agent surfaces run under syscall-isolated runtimes that don't host a Docker daemon. When a task needs to actually **run** — `docker compose up`, full stack boot, a browser-reachable UI — dispatch a **Coder workspace** and drive it.

Use this skill when:
- A task requires running the project's full app, not just editing code or unit tests
- The operator asks to demonstrate work in a browser
- You need a stable URL to hand back for poking around

Don't use it for pure code editing, unit tests / linting, or git — those stay in the agent surface.

## Two ways to reach Coder

Coder exposes its **own** MCP server (Coder-maintained; no custom wrapper). Reach it whichever way your harness is wired:

| Path | Who | How |
|------|-----|-----|
| **MCP tools** (default) | **any client** whose VK holds the `coder` access group (Claude Code, pi, OpenClaw agents) | The platform federates Coder's remote MCP through the LLM gateway. Tools surface as `coder_*` (via the gateway, prefixed — e.g. `coder-coder_create_workspace`, plus your harness's own MCP prefix). No CLI, no token handling — the gateway injects auth. |
| **`coder` CLI** | **pi** (CLI bundled in the pi-web / pi-worker images) | `CODER_URL` + `CODER_SESSION_TOKEN` are pre-set (admin token via ExternalSecret from `op://<vault>/<item>/<field>`); every subcommand uses them, no `coder login`. Call via `bash`. |

If the `coder_*` tools aren't visible to you, your VK lacks the `coder` group (see your platform's access-map skill) — fall back to the CLI only if your harness bundles it, else say so.

### The MCP path is one *shared* identity — check whose

"The gateway injects auth" does **not** mean the grant is scoped to you. Coder's remote MCP is federated with a **single static token**, so every client holding the `coder` group inherits that one identity — there is no per-surface identity and no per-workspace authorization. If that token belongs to a deployment owner, any holder can act on **any** workspace, including ones it didn't create.

One call tells you where you stand:

```
coder_get_authenticated_user   # → username + roles; owner/admin means unscoped reach
```

Treat that as a precondition before any destructive operation, and assume other surfaces share your identity when reasoning about blast radius.

## Core operations (MCP tool ↔ CLI)

| Operation | MCP tool | CLI |
|-----------|----------|-----|
| List your workspaces | `coder_list_workspaces` | `coder list --output json` |
| Inspect one | `coder_get_workspace` | `coder show <ws> --output json` |
| **Create / claim** | `coder_create_workspace` (pass every template parameter) | `coder create --yes --template <t> --parameter …` |
| Start / **stop / delete** | `coder_create_workspace_build` (`transition: start\|stop\|delete`) — **one tool; delete rides along with start/stop, see below** | `coder start` / `coder stop --yes` / `coder delete --yes` |
| **Run a command (exec)** | `coder_workspace_bash` | `coder ssh <ws> -- bash -lc "<cmd>"` |
| List / read / write / edit files | `coder_workspace_ls` / `coder_workspace_read_file` / `coder_workspace_write_file` / `coder_workspace_edit_file(s)` | `coder ssh <ws> -- …` |
| App URLs / port-forward | `coder_workspace_list_apps` / `coder_workspace_port_forward` | `coder show`… / `coder port-forward` |
| Build / agent logs | `coder_get_workspace_build_logs` / `coder_get_workspace_agent_logs` | `coder logs <ws>` |
| Templates (read-only) | `coder_list_templates` / `coder_get_template` / `coder_template_version_parameters` | `coder templates list` |

**Scope note (MCP):** the federated `coder` server is deliberately scoped — workspace lifecycle + exec + file ops + logs + **read-only** templates. Template *creation/mutation* and Task tools are intentionally excluded from the MCP surface; if you truly need them, that's a CLI/operator step, not this tool path.

**Pass every template parameter explicitly.** Coder does not auto-default unset parameters — via the CLI it prompts interactively (and dies `prepare build: EOF` with no stdin); via MCP an omitted required parameter fails the build. Use `coder_template_version_parameters` / `coder templates` to learn the parameter set first (e.g. an `envbuilder` template typically declares `git_url`, `git_ref`, `cpu_cores`, `memory_gb`).

## Pattern: demonstrate a code change

1. Edit + commit + push to a feature branch (agent surface).
2. **Create** a workspace from the branch — `coder_create_workspace` with `git_ref=<branch>` + all params.
3. **Wait for the agent** — the workspace pod can be `Running` before the in-workspace Coder agent registers. Poll `coder_get_workspace` until the agent is ready (CLI: `coder ping <ws> --wait`). `envbuilder` cold start (kaniko devcontainer build) is 1–3 min — normal; don't retry create.
4. **Run** the stack — `coder_workspace_bash` `cd /workspaces/<repo> && docker compose up --build -d` (use `-d` so the call returns).
5. **Hand back the URL** — `coder_workspace_list_apps`, or the wildcard pattern `<ws>--<owner>.<coder-host>` (owner for the in-cluster admin token is the deployment's Coder admin user).
6. After validation, free resources — but pick the transition deliberately:
   - **`stop` is always safe.** It releases compute and keeps any persistent home intact.
   - **`delete` is safe only for a workspace whose template has no persistent volume.** On a durable template it destroys an unrecoverable volume.

   Ephemeral dispatch should **target the ephemeral template by name**, not whatever template is handy: creating from a *durable* template mints a volume a template-scoped reaper will deliberately not reclaim.

## Gotchas (apply to both paths)

- **Template must exist first.** Create only instantiates existing templates; new ones are pushed via the deployment's template-sync workflow when a template definition changes (example layout: an `infrastructure/coder/templates/<name>/main.tf`). Unknown template → build step first, not this skill.
- **Workspace URL = wildcard subdomain.** With `*.<coder-host>` configured, every workspace is reachable at `<ws>--<owner>.<coder-host>`.
- **Repo clone silently failed → fallback image.** If the workspace has no `/workspaces/<repo>`, envbuilder fell back to `codercom/enterprise-base:ubuntu` (git clone failed — often a template setting `GIT_USERNAME` without `GIT_PASSWORD`, rejected for public repos). The workspace boots but has no devcontainer features (no docker-in-docker, node, etc.). Check `coder_get_workspace_build_logs` / `kubectl logs -n <coder-namespace> coder-<owner>-<ws>`.
- **On the fallback image there is no `gh`, and `git push` *hangs*.** This is the previous gotcha's second-order effect and it's worse than an error. Templates commonly wire credentials with `gh auth setup-git` guarded by `command -v gh`; on a fallback build the guard silently skips, git ends up with **no credential helper**, and a push blocks on an interactive credential prompt — burning the whole tool-call timeout with no diagnostic. The tell is `git config --get credential.helper` returning empty. Work-around, since a token is usually still in the environment:
  ```bash
  git -c credential.helper='!f(){ echo username=x-access-token; echo password=$GH_TOKEN; };f' \
      push -u origin <branch>
  ```
  **Habit that avoids it entirely: verify your first push early in the session**, not at the end when the work exists.
- **`coder_create_workspace_build` bundles delete — a name-based allowlist cannot filter it.** `transition` is an *argument*, and gateway `allowed_tools` filters by tool **name**. So "allow start and stop but never delete" is **not expressible** at the gateway: allowlisting this tool for lifecycle management also allowlists destruction. Fine for an ephemeral tier; not fine once a durable tier exists. See `litellm-routing-model` for the general form of this hole.
- **PodSecurity must allow privileged.** The Coder workspaces namespace runs `enforce: privileged` so envbuilder's kaniko step can go `privileged: true` inside kata isolation. `forbidden: violates PodSecurity` on build → the namespace label was reverted.

## Two tiers: scratch vs durable

Any consumer running both an agent surface and Coder has two development tiers, whether or not it has named them: a **scratch tier** (the agent surface's own pod-local checkout) and a **durable tier** (a workspace with a persistent home).

**Escalate scratch → durable when** the work spans sessions · it needs a real runtime (Docker, full boot, browser UI) · the working set outgrows the scratch pod's ephemeral ceiling · the build or cache is the expensive part.

**Git is the migration medium, always.** The two tiers essentially never share storage — one is pod-local, the other typically an RWO node-pinned volume in another namespace — so `git push` / `git fetch` is the handoff. State this explicitly because the failure is quiet: **`git stash` does not cross tiers** (it's pod-local), and it's the first thing people reach for.

**Neither tier is a backup.** A durable home is usually on a `Delete`-reclaim, node-pinned class with no snapshot behind it. Push-early doctrine is what makes the durable tier safe — which is exactly why the credential-hang gotcha above matters so much.

The concrete template names, volume classes, and reaper policy are deployment-specific — they live in the consumer's own dev-environment-tiers local skill.

## Related

- your platform's access-map skill — which VKs hold the `coder` group + the gateway/host values
- your platform's conventions skill — cluster operating rules (tolerations, fsGroup, PodSecurity)
- `litellm-routing-model` — why `allowed_tools` can't gate the `delete` transition
