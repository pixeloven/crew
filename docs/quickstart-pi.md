# Quickstart — pi.dev

## 1. Install the package

In `.pi/settings.json` — pin the tag for reproducible builds:

```json
{ "packages": ["npm:pi-subagents@0.33.1", "git:github.com/pixeloven/crew@v0.33.0"] }
```

Bump the pin to update; the release tag list is the changelog.

## 2. Verify — do this, don't assume

```
/subagents-doctor
```

It should list the seven crew agents (`lead`, `triage`, `investigator`, `researcher`, `responder`, `reviewer`, `implementer`) alongside pi's built-ins, and show the foundation's skills loaded from the package's `skills/` tree.

> **Why this step is not optional.** Package **agent** discovery and package **skill** discovery are separate mechanisms with separate manifest keys, and a wrong agents key fails *silently* — skills load, agents don't, and nothing errors. This foundation shipped exactly that bug until v0.13.0 (the manifest declared `pi.agents`, which neither pi core nor pi-subagents reads). If the doctor lists skills but no crew agents, check the package's manifest key before anything else.
>
> **And it shipped a second, identical-looking one until v0.35.0.** pi-subagents resolves an agent's name *strictly* from frontmatter `name:` — there is no filename fallback — and drops any file lacking it with `continue`, no diagnostic. Every rendered pi role omitted `name:`, so the entire fleet was invisible while `pi-agents/` looked perfectly correct on disk. Both failures present identically at the doctor: skills yes, agents no. If you are pinned below v0.35.0, this is why.

Package agent discovery requires `pi-subagents` **≥ 0.29.0**.

## 3. The behavioral contract — where it lives

pi workers read the **repo-root `AGENTS.md`** directly from the checkout — the same file Claude Code reads (no `CLAUDE.md` shim needed; that file is Claude-specific). One contract drives both harnesses. If the repo has no `AGENTS.md` yet, run onboarding from any harness that can write (or copy `templates/AGENTS.md` and fill the ▸ blocks).

## 4. The overlay

The project's own additions live in `.pi/skills/` and `.pi/agents/` — pi walks from cwd to the git root **before** the package, so local entries shadow foundation ones on name collision. Your project-specific values (topology, conventions, secret paths) belong there as local skills; starter stubs live in the foundation's `templates/local-skills/`.

## Notes for autonomous workers

- Workers run with the pi frontmatter's `tools:` allowlist, which mirrors the Claude Code denylist rendered from the same `role.yml`. Read-only roles get no `write`/`edit` — but they do get `bash`, so the allowlist makes writing *inconvenient*, not impossible. The prose in the role body is the real constraint; enforce the rest with pi's permission system if your runtime needs a hard boundary.
- Implementer ships assuming the **interactive** case: it creates branches, commits, pushes and opens PRs itself. If you dispatch it from an autonomous runtime that prepares the workspace and pushes on its behalf, shadow `implementer.md` in `.pi/agents/` with your runtime's operating context — that contract is a property of your deployment, so the foundation no longer guesses at it.
- Capability availability (KB, search, image gen, …) is granted by the worker's LiteLLM virtual key, not by installing skills — see the project's gateway-routing local skill. The `doctor` skill reports what a session can actually reach.
