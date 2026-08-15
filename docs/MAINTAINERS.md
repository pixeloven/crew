# Maintainers

How the foundation itself is built, versioned, and kept honest. Consumers don't need this page — start from the [README](../README.md) and the quickstarts.

## Layout

```
harmony-crew/
├── roles/<role>/                   # SINGLE SOURCE for the 7 role agents (body + per-runtime frontmatter)
│   └── expected-local-skills.txt   # backtick-token allowlist: local-skill names agent bodies may cite as examples
├── skills/<name>/SKILL.md          # one tree → all three harnesses read it (schema-v2 frontmatter)
├── agents/*.md                     # RENDERED Claude subagent files (do not edit)
├── pi-agents/role-*.md             # RENDERED pi-subagents files (do not edit)
├── docs/CATALOG.md                 # GENERATED skill inventory
├── templates/AGENTS.md             # the onboarding scaffold (behavioral spine + ▸ Fill blocks)
├── templates/local-skills/         # the 7 consumer-local slot definitions + starter stubs
├── scripts/render_roles.py         # role renderer; --check is the CI drift gate
├── scripts/gen_catalog.py          # docs/CATALOG.md generator; --check in CI
├── scripts/check_skills.py         # schema-v2 frontmatter validator (incl. expects-local)
├── scripts/check_skill_refs.py     # every skill ref in agent bodies must resolve
├── package.json                    # pi package manifest
└── .claude-plugin/
    ├── plugin.json                 # Claude plugin manifest
    └── marketplace.json            # this repo doubles as its own marketplace
```

## Editing rules

- **Roles:** edit `roles/<role>/` (shared `body.md`, per-runtime `claude.yml`/`pi.yml`, optional `{{RUNTIME_CONTEXT}}` appendix), run `scripts/render_roles.py`, commit source + rendered output together. CI fails on drift.
- **Skills:** schema-v2 frontmatter (`name`, `description` ≥110 chars with trigger language, `tier`, `requires`, optional `expects-local`). No project-specific values — the dividing test is **"no project context baked in"**, not width: a single-language convention skill is fine if any project benefits; anything binding to one deployment's vault, gateway, cluster, secret paths, or domains belongs in that consumer's overlay (deferral goes through an `expects-local` slot).
- **Generated artifacts:** after any frontmatter change, run `scripts/gen_catalog.py` and commit `docs/CATALOG.md`.
- **Discovery is the harness's job, not ours.** pi builds an `<available_skills>` block from every loaded skill's name + description (`core/skills.js`); Claude Code and Codex render equivalent listings. So the catalogue needs no in-repo index — one would be a second, staler copy of what the runtime already injects, and on Codex it would compete for a **budgeted** skills listing that silently truncates descriptions and omits skills when the catalogue grows. That is why `description` quality is a hard gate here and why the catalogue stays small: those are the only two levers on discovery that actually exist.

## Versioning

One semver line drives all consumers. Claude Code re-fetches only when `plugin.json`'s `version` changes, so **every PR that touches `skills/`, `agents/`, `pi-agents/`, `roles/`, or `templates/` bumps the version in the PR itself** (usually the patch; set minor/major explicitly when warranted) — enforced by the `version-bump` check in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). On merge, [`.github/workflows/release.yml`](../.github/workflows/release.yml) tags the merged version — tag-only; it pushes nothing to `main`. Keep `plugin.json` == `package.json` == git tag `vX.Y.Z`. **Claude Code** tracks `main` (always latest); **pi.dev** and **Codex** pin the tag (reproducible) — bump the pin to update.

## CI gates

`validate` (manifests + schema-v2), `roles-rendered` (render drift + skill-ref resolution), `generated-current` (catalog freshness + templates parse), `version-bump` (on content change), plus the security floor (gitleaks, osv-scanner, dependency-review). This repo is a **supply-chain root** — its skills and agents load as instructions into every consumer's agents; every change requires owner review.
