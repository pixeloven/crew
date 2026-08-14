# Quickstart — OpenClaw

OpenClaw agents are project **personas**, not crew roles — they don't load the plugin/package or read `AGENTS.md`. They consume the **consumption slice**: the small set of skills that let a persona *use* the platform (web search, image generation, knowledge-base access). The slice is machine-derived from skill frontmatter into [`slices/openclaw.txt`](../slices/openclaw.txt) — never hand-maintain the list.

## 1. Install the slice into the gateway

The gateway's `init-skills` step clones the foundation at a pinned tag and installs whatever the slice file names:

```sh
# init container (a GH token is needed only for a PRIVATE foundation repo; mount it init-only)
git clone --depth 1 -b v0.12.0 https://<token>@github.com/ductiletoaster/harmony-crew /tmp/hc
while read -r s; do
  openclaw skills install /tmp/hc/skills/$s --global --as $s      # → ~/.openclaw/skills (auto-loaded)
done < /tmp/hc/slices/openclaw.txt
```

Bumping the tag updates both the skills *and* the slice membership in one move.

## 2. Scope per-agent visibility

Installed skills are globally available; each agent sees only what its allowlist names. In the gateway config:

```yaml
agents:
  list:
    - id: <persona-id>
      skills: [searxng-search, comfyui, knowledge-base-access]   # subset of the slice
```

Give an agent only the slice entries matching capabilities its virtual key actually holds — a skill without the matching VK access group is instructions for tools the agent can't see.

## 3. Grant the capabilities

Skills are the *guidance*; the LiteLLM **virtual key grants the tools**. For each capability (search, image gen, KB), add the access group to the agent's VK per the capability-parity pattern in `litellm-routing-model`, then **restart the gateway pod** — it caches its MCP tool list at startup.

## 4. Verify

From a persona conversation: ask for a web search, an image, and a KB lookup. Each should either work or fail with a missing-tool error — the latter means the VK grant (step 3) or the allowlist (step 2) is missing, not the skill install.

Operator-side skills for *building and tuning* gateways (`openclaw-platform-operations`, `openclaw-agent-tuning`) stay in the Claude Code / pi.dev harness — never install them into personas.
