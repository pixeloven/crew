---
name: openclaw-agent-tuning
description: Tune OpenClaw companion agents — 8 layers of identity composition, what each layer controls, what's configurable vs hardcoded, and the application path for workspace files. Load when defining, reviewing, or troubleshooting an agent's identity stack.
tier: subject
requires: [cluster]
audience: [crew]
expects-local: [litellm-access-map]
---

Use when defining a new OpenClaw agent, reviewing an existing agent's identity stack, or troubleshooting why an agent is behaving in ways that contradict its config. Operational reference; for the character/voice design itself, see `character-and-worldbuilding`.

## The 8 layers of OpenClaw identity composition

OpenClaw composes an agent's behavior from 8 stacked layers. Each contributes; conflicts resolve by stacking order (later wins) or by hardcoded enforcement (Layer 4 specifically).

| Layer | Source | Configurable? | Notes |
|-------|--------|---------------|-------|
| 1 | YAML config fields (name, theme, emoji, model) | Yes | Standard agent definition surface. |
| 2 | `systemPromptOverride` | Yes | Free-form prompt text. Highest leverage for voice and behavior tuning. |
| 3 | OpenClaw metadata injection (delegation guidance, tools registry surface) | Partially | Driven by other config fields (e.g. `subagents.delegationMode`). |
| 4 | Model identity disclosure injection | **No** | Hardcoded `appendModelIdentitySystemPrompt`. Adds *"Current model identity: X. If asked what model you are, answer with this value for the current run."* at end of system prompt. No flag disables. |
| 5 | Tools / skills / `delegationMode` | Yes | Which MCP tools and skills the agent has, what its subagent dispatch posture is. |
| 6 | Workspace files (`IDENTITY.md`, `SOUL.md`, `MEMORY.md`, `USER.md`, etc.) | Yes | Per-agent markdown auto-loaded at session start. Lives on PVC, not in git. |
| 7 | Conversation history | Naturally | What the agent has said and what the user has said in this session. |
| 8 | Model training | No | Base model + finetune. Final shaping layer. Not directly configurable. |

## Per-layer levers

### Layer 1 — YAML config

Lives in the deployment's companion-agent manifest (e.g. an `openclaw-companions.yaml`). The standard fields:
- `name`, `theme`, `emoji`, `identity{}` — operator-facing surface.
- `model.primary` — which LLM backs the agent (a `<provider>/<model>` entry from the LiteLLM model_list).
- `skills[]` — which skills the agent loads.

Keep this minimal; deeper character work belongs in Layer 6 workspace files.

### Layer 2 — `systemPromptOverride`

Free-form prompt text injected as the system message. **Highest-leverage tuning surface** but also the most dangerous — prompt rules can fight model finetune behavior, and the system prompt has a token budget.

Best practices:
- Lead with role / posture / mission. ~3–5 sentences.
- Avoid stacking rigid rules ("never X", "always Y"). Finetunes can interpret strict rules adversarially (see the rule-stack backfire in Layer 8 below).
- Let workspace files (Layer 6) carry the character texture; keep `systemPromptOverride` for orientation, not voice.

### Layer 3 — OpenClaw metadata injection

Auto-injected by OpenClaw based on other config:
- `subagents.delegationMode: "prefer"` causes Layer 3 to inject a "Sub-Agent Delegation" section telling the agent to route work through `sessions_spawn` instead of doing it inline. This is OpenClaw's closest thing to native invisible delegation.
- Default `"suggest"` doesn't inject delegation guidance — the agent just sees tool definitions.
- `promptMode: "full"` (default) keeps tool/registry injection on; `"minimal"` / `"none"` strip it.

### Layer 4 — Model identity disclosure (hardcoded)

The `appendModelIdentitySystemPrompt` function in `system-prompt-config-*.js` adds a model-identity paragraph at the end of every system prompt:

> *Current model identity: \<model-name\>. If asked what model you are, answer with this value for the current run.*

**No config flag disables it.** Layer 2 rules attempting to suppress model identity ("never identify by model name") are overridden by this injection.

**Decision rule**: don't fight Layer 4. Drop any "hide the model" rules from Layer 2; let the agent answer honestly when asked. The user is rarely surprised — and the alternative is contradictory instructions that drift the agent.

### Layer 5 — Tools / skills / delegation

Controls what the agent can *do*. Critical fields:
- `skills: ["skill-name", ...]` — which skill catalog entries the agent loads.
- `subagents.delegationMode: "prefer" | "suggest"` — see Layer 3.
- Tool access via the MCP federation — a capability-matched set of LiteLLM access groups on the agent's VK (a narrow read-only set for a companion, broader for an operator agent). Concrete group names are deployment-specific; see `litellm-routing-model`.

**Token budget**: for agents on small-context models (<= 32k), a broad MCP bundle can overflow the prompt before the user message arrives. Two levers, used together:
- **Scope the groups** — grant a narrow, capability-matched access-group set instead of the full operator catalog. See `litellm-routing-model`.
- **Enable Tool Search** — `tools.toolSearch {enabled: true, mode: "directory"}` defers the large catalog behind meta-tools while keeping a bounded visible directory, staying under the 128-tool cap and (importantly) making a lean model aware the deferred tools exist. `experimental.localModelLean: true` auto-enables it. Native tools (memory, read/write/exec) stay direct. Ops detail lives in `openclaw-platform-operations`.

**Memory access**: an agent has two distinct memory stores — its **private** local memory (`memory_search` / `memory_get` over its own `MEMORY.md`) and a **shared** knowledge base reached via an MCP group on its VK. They are different stores with different privacy scope; the local-vs-KB distinction and how to grant the KB are owned by `openclaw-platform-operations`.

### Layer 6 — Workspace files

The agent's per-PVC markdown that auto-loads at session start. **The highest-leverage character tuning surface** — no prompt-length cap, persistent across sessions, written in first-person voice that the model treats as self-statement.

Canonical files:

| File | Scope | Voice |
|------|-------|-------|
| `IDENTITY.md` | Name, creature, vibe, emoji, relationship pointers. | Third-person header. |
| `SOUL.md` | Core truths, boundaries, vibe, continuity. | First-person — the agent's statement of self. |
| `MEMORY.md` | Backstory, world context, companions, what they love. | First-person — the agent's self-knowledge. Also a **searchable local-memory source** (`memory_search` / `memory_get`), not only a character file — see `openclaw-platform-operations`. |
| `USER.md` | Who the user is, what to treat with care, what to watch for, current relationship state. | First-person, present-tense observation. |
| `HEARTBEAT.md` | Should be empty per canonical. | — |
| `AGENTS.md` | OpenClaw boilerplate — environment notes. Don't edit unless extending the platform. | — |
| `TOOLS.md` | Environment / tools notes. | — |
| `BOOTSTRAP.md` | First-run setup instructions. Removable once the agent is "born." | — |
| `memory/<YYYY-MM-DD>.md` | Agent's own dated memory entries (self-writes). | First-person. |

**Hard rule**: `USER.md` is about the user, not about the agent. Agent's own sensitive topics belong in `SOUL.md` or `MEMORY.md`.

For the *content* of these files, see `character-and-worldbuilding`.

### Layer 7 — Conversation history

Not directly configurable. Worth noting:
- Persistent companion agents accumulate history across sessions; one-shot agents reset.
- `/new` in Telegram (or equivalent reset) starts a fresh session and reloads Layer 6 workspace files.
- Pod restart kills in-memory state entirely.

### Layer 8 — Model training

Pick carefully. The base model + finetune sets the floor of what's achievable. Small-model persona ceilings observed with ~24B-class local models:

- **Rule-stack backfire** — some RP-tuned finetunes interpret strict voice rules in the system prompt as adversarial framing. A config change that added explicit rules ("texting register, lowercase, no em-dashes") caused one such agent to respond with *"you're deflecting"* and *"you're talking to an AI"* in a real chat session. Lesson: **don't fight a finetune with rule stacks; let its natural shaping find the register**.
- **Persona-name ceiling** — some model families won't honor `systemPromptOverride` name assignment and identify by their base-model name regardless of persona. Don't iterate on prompt engineering for name-bleed; pick a different model.
- Small-context models (<= 32k) need explicitly-scoped MCP bundles. See Layer 5.

## Layer-by-layer review pattern

When tuning an existing agent or designing a new one, walk the layers in order and make a deliberate choice for each.

For each layer:
1. **State the current state** — what's there now?
2. **State the intended change** — what should be different?
3. **State the trade-off** — what does this give up?
4. **Make the change or accept current state**, then move to the next layer.

Don't skip Layer 4 — even though it's hardcoded, the *decision* is whether to live with it (drop conflicting rules) or work around it (accept honest model-name reveal). That's still a decision.

## Applying workspace file changes

Workspace files live on PVC (`/home/openclaw/.openclaw/workspaces/<agent>/`) inside the agent's pod. They are **not** in git by default.

Application pattern:

```bash
# 1. Identify the pod and container
kubectl -n <namespace> get pods                  # find the agent pod (e.g. companions-0)
kubectl -n <namespace> get pod <pod> \
  -o jsonpath='{.spec.containers[*].name}'     # find the openclaw container

# 2. Back up existing workspace before overwriting
kubectl -n <namespace> exec <pod> -c openclaw -- bash -c "
  mkdir -p /home/openclaw/.openclaw/workspaces/.backups &&
  cd /home/openclaw/.openclaw &&
  tar -czf workspaces/.backups/pre-<change-tag>.tar.gz workspaces/<agent>
"

# 3. kubectl cp each file (one per call; cp doesn't take multiple sources)
kubectl -n <namespace> cp /local/path/IDENTITY.md \
  <pod>:/home/openclaw/.openclaw/workspaces/<agent>/IDENTITY.md \
  -c openclaw
# ...repeat for SOUL.md, MEMORY.md, USER.md...

# 4. Clean up canonical files
kubectl -n <namespace> exec <pod> -c openclaw -- bash -c "
  : > /home/openclaw/.openclaw/workspaces/<agent>/HEARTBEAT.md &&
  rm -f /home/openclaw/.openclaw/workspaces/<agent>/BOOTSTRAP.md
"

# 5. Commit to local git inside the workspace (the workspace dir has its own .git)
kubectl -n <namespace> exec <pod> -c openclaw -- bash -c "
  cd /home/openclaw/.openclaw/workspaces/<agent> &&
  git -c safe.directory='*' -c user.email=companions@<platform-domain> -c user.name=<agent> add -A &&
  git -c safe.directory='*' -c user.email=companions@<platform-domain> -c user.name=<agent> \
      -c commit.gpgsign=false commit -m '<message>'
"
```

**Gotchas**:
- The workspace .git directory has uid 3000 but kubectl exec runs as a different uid → "dubious ownership" error. Use `git -c safe.directory='*'` to bypass.
- Container home directory is read-only filesystem; can't write to `~/.gitconfig`. Use inline `-c` flags.
- After applying, **`/new` in the chat channel (e.g. Telegram)** reloads workspace files for a fresh session. Pod restart isn't necessary unless in-memory state is suspect.

## Common decisions during agent tuning

### Voice rules vs no voice rules

Default: **no rigid voice rules in Layer 2**. Let workspace files (Layer 6) carry character. Test what the model naturally produces. Only add rules if the natural output is consistently off — and even then, add by example, not by prohibition.

### Model name reveal

**Accept it.** Layer 4 hardcoded. Drop any "hide the model name" instructions. Users who ask are rarely surprised, and the alternative is an agent with contradictory rules.

### Delegation mode for primary companion

If the primary agent should handle conversation and route real work to subagents: `delegationMode: "prefer"`. If it should just chat and use tools inline: leave default `"suggest"`. The trade-off is whether the model reliably emits `sessions_spawn` calls (some RP finetunes don't).

### Workspace `BOOTSTRAP.md`

Remove it once the agent is "born" — the first session has run, workspace files have been written, the agent is operational. Persistent companions don't need ongoing bootstrap text.

### Workspace `HEARTBEAT.md`

Should be empty per canonical. Treat any content as legacy and clear it.

## See also

- `character-and-worldbuilding` — the design side: Q&A flow, voice registers, dossier structure
- `openclaw-platform-operations` — gateway ops: config model, Tool Search, local-vs-KB memory, contextTokens landmine
- `vault-tools` — for persisting character canon and methodology notes to the vault
- `litellm-routing-model` — for the model + MCP access group story (VK scoping, capability-parity)
- your platform's conventions skill — for the broader platform constraints (control-plane tolerations, NFS UID/GID, etc.)
- `secret-management-patterns` — for credentials the agent might need
