# Local-skill slots — what a consumer supplies

Foundation skills teach *general patterns* and deliberately stop at the point where a
value is deployment-specific. Each such deferral targets a named **slot** — a
consumer-local skill that holds the concrete values for that deployment. Skills declare
the slots they defer to in `expects-local:` frontmatter; Crew Doctor derives and
reports which applicable slots a project has not yet filled.

A consumer fills a slot by creating a local skill in its overlay
(`.agents/skills/<name>/SKILL.md`, symlinked into `.claude/skills/`) — conventionally
named `<project>-<slot>`, though any name works. What matters is that the content
exists locally and the project's `AGENTS.md` concern → local-skill map points at it.
Local skills **shadow** foundation skills on name collision in pi's flat namespace;
under Claude Code and Codex the plugin copy is namespaced `crew:skill`, so both are visible.

| Name | Type | Holds |
|---|---|---|
| `platform-conventions` | declared slot | scheduling, storage tiers, security context, secret-sync and namespace policy |
| `topology` | declared slot | nodes, addresses, service domains, DNS model, expected state |
| `protected-seams` | declared slot | patterns that require human sign-off |
| `secret-paths` | declared slot | non-secret references to credential stores and paths |
| `agent-runtime` | declared slot | autonomous exit codes, result format, retry, and dispatch contracts |
| `litellm-access-map` | recommended vocabulary | concrete virtual-key ↔ access-group mapping |
| `vault-ops` | recommended vocabulary | corpus lint/promote jobs, schedules, and placement conventions |

Each `<slot>.md` file in this directory is a starter stub — copy it into your overlay,
rename, and fill the ▸ blocks.

**Two kinds of slot.** Five of these are *declared* — a foundation skill names them in its
`expects-local` frontmatter, so the doctor can report them as unfilled: `platform-conventions`,
`topology`, `protected-seams`, `secret-paths`, `agent-runtime`. The other two —
`litellm-access-map` and `vault-ops` — are *recommended vocabulary*: no foundation skill defers
to them (the skills that did now live in consumer overlays), but they name concerns most
platform-running consumers have, and using the same names keeps overlays legible to each other.
Both kinds are valid in `expects-local` if your own skills want to declare them.
