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
A [pack](../../docs/PACKS.md) skill can also fill a slot by declaring `provides:`.
When both a local skill and a pack fill the same slot, the local one outranks the pack.
A pack may also declare slots of its own, each with a stub in the pack's own
`templates/local-skills/`; fill those the same way ([Pack-owned slots](../../docs/PACKS.md#pack-owned-slots)).
Local skills **shadow** foundation skills on name collision in pi's flat namespace;
under Claude Code and Codex the plugin copy is namespaced `crew:skill`, so both are visible.

| Name | Type | Holds |
|---|---|---|
| `platform-conventions` | declared slot | scheduling, storage tiers, security context, secret-sync and namespace policy |
| `topology` | declared slot | nodes, addresses, service domains, DNS model, expected state |
| `protected-seams` | declared slot | patterns that require human sign-off |
| `secret-paths` | declared slot | non-secret references to credential stores and paths |
| `agent-runtime` | declared slot | autonomous exit codes, result format, retry, and dispatch contracts |
| `decision-record-format` | declared slot | decision-record (ADR) location, numbering, template, and status values |

Each `<slot>.md` file in this directory is a starter stub — copy it into your overlay,
rename, and fill the ▸ blocks. Onboarding proposes that copy for every unfilled slot, and
Doctor reports a fill that still carries ▸ blocks as partial.

**Declared slots.** All six are *declared* — a foundation skill names them in its
`expects-local` frontmatter, so the doctor can report them as unfilled: `platform-conventions`,
`topology`, `protected-seams`, `secret-paths`, `agent-runtime`, `decision-record-format`. They are the only Crew names
valid in `expects-local`. A concern specific to one platform (an LLM gateway's access map, a
corpus's jobs) belongs in a local skill of your own, which your `AGENTS.md` map points at; it
needs no Crew slot.
