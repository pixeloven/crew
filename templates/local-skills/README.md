# Local-skill slots — what a consumer supplies

Foundation skills teach *general patterns* and deliberately stop at the point where a
value is deployment-specific. Each such deferral targets a named **slot** — a
consumer-local skill that holds the concrete values for that deployment. Skills declare
the slots they defer to in `expects-local:` frontmatter; the Phase-4 onboarding doctor
reports which slots a project has not yet filled.

A consumer fills a slot by creating a local skill in its overlay
(`.agents/skills/<name>/SKILL.md`, symlinked into `.claude/skills/`) — conventionally named `<project>-<slot>` (Harmony's `platform-conventions`
slot is filled by `harmony-platform-conventions`), though any name works: what matters
is that the content exists locally and the project's `AGENTS.md` skill index points at it.
Local skills **shadow** foundation skills on name collision in pi's flat namespace; under Claude Code the plugin copy is namespaced `plugin:skill`, so both are visible.

| Slot | Holds | Harmony's filling (the worked example) |
|---|---|---|
| `platform-conventions` | tolerations, StorageClass tiers, security contexts, ESO patterns, namespace policies | `harmony-platform-conventions` |
| `topology` | node names/IPs, service domains, DNS model, expected cluster state | `homelab-topology` |
| `protected-seams` | the project's seam registry — which patterns need human sign-off | `harmony-protected-seams` |
| `litellm-access-map` | the concrete VK↔access-group matrix, key aliases, team names | `litellm-access-map` |
| `secret-paths` | the concrete `op://` (or equivalent) paths, vault names, store names | (folded into Harmony's conventions/ops skills) |
| `vault-ops` | KB lint/promote job names + schedules, corpus conventions, extraction model | (folded into Harmony's operations skill) |
| `agent-runtime` | the autonomous runtime's contracts — exit codes, result format, dispatch CLI | `agent-orchestration-patterns` + `argo-workflows-patterns` |

Each `<slot>.md` file in this directory is a starter stub — copy it into your overlay,
rename, and fill the ▸ blocks.

**Two kinds of slot.** Five of these are *declared* — a foundation skill names them in its
`expects-local` frontmatter, so the doctor can report them as unfilled: `platform-conventions`,
`topology`, `protected-seams`, `secret-paths`, `agent-runtime`. The other two —
`litellm-access-map` and `vault-ops` — are *recommended vocabulary*: no foundation skill defers
to them (the skills that did now live in consumer overlays), but they name concerns most
platform-running consumers have, and using the same names keeps overlays legible to each other.
Both kinds are valid in `expects-local` if your own skills want to declare them.
