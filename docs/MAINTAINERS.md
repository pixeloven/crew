# Maintainers

How the foundation itself is built, versioned, and kept honest. Consumers don't need this page — start from the [README](../README.md) and the quickstarts.

## Layout

```
crew/
├── roles/<role>/                   # SINGLE SOURCE for the 7 role agents — exactly role.yml + body.md
│   └── expected-local-skills.txt   # backtick-token allowlist: local-skill SLOT names agent bodies may cite
├── skills/<name>/SKILL.md          # one tree → all three harnesses read it (schema-v2 frontmatter)
├── agents/*.md                     # RENDERED Claude subagent files (do not edit)
├── pi-agents/*.md                  # RENDERED pi-subagents files (do not edit) — same names as agents/
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

- **Roles:** a role is exactly two files — a harness-neutral `role.yml` (`name`, `description`, `writes`, optional `dispatch`) and one shared `body.md`. Anything else in the directory is a build error. Run `scripts/render_roles.py`, commit source + rendered output together; CI fails on drift. `agents/` and `pi-agents/` are byte-identical below the frontmatter, and `render_roles.py` alone translates the posture into each harness's dialect (Claude Code denies via `disallowedTools`, pi allows via `tools`), so the two cannot drift apart by editing.
- **Per-harness prose is a smell; per-deployment prose is a bug.** Roles used to carry `claude-context.md` / `pi-context.md` appendices. What they actually encoded was not a harness difference but a *runtime* one — an interactive working tree versus a workflow-managed pod — and the pi copy had accumulated one consumer's Argo paths, branch naming and exit contract. The portable default is now the interactive case, in the shared body; a deployment whose runtime differs shadows the rendered agent in **its own overlay**. If you find yourself wanting a per-harness paragraph, check first whether the real axis is the deployment.
- **No runtime knobs in a role.** A role declares who it is and what it may touch — never which model, how hard to think, or how many turns it gets. All three harnesses support those (Claude Code: `model` / `effort` / `maxTurns`; pi: `model` / `thinking` / `turnBudget`; Codex: `model` / `model_reasoning_effort`) and all three inherit sensible values from the dispatching session when they are omitted. Shipping them from a foundation imposes one operator's cost tier and one vendor's model naming on every consumer, and goes stale on every model release. On Codex it is worse than stale: a role file's `model` is applied *after* the spawn arguments, so it silently overrides the orchestrator's explicit choice. `render_roles.py` rejects `model`, `thinking`, `effort`, `model_reasoning_effort`, `turnBudget` and `maxTurns` in `role.yml` by name — a consumer that wants to pin one sets it in its own overlay or harness config, where it belongs.
- **Skills:** schema-v2 frontmatter (`name`, `description` ≥110 chars with trigger language, `tier`, `requires`, optional `expects-local`). No project-specific values — the dividing test is **"no project context baked in"**, not width: a single-language convention skill is fine if any project benefits; anything binding to one deployment's vault, gateway, cluster, secret paths, or domains belongs in that consumer's overlay (deferral goes through an `expects-local` slot).
- **Generated artifacts:** after any frontmatter change, run `scripts/gen_catalog.py` and commit `docs/CATALOG.md`.
- **Discovery is the harness's job, not ours — and that is a dependency, so it gets verified and dated.** Each supported harness lists installed skills, with their descriptions, to the model itself. Verified 2026-08-15:

  | Harness | Mechanism | Evidence |
  |---|---|---|
  | pi.dev 0.84.1 | `formatSkillsForPrompt` → `<available_skills>` with name/description/location | `core/skills.js:257-278` |
  | Claude Code | system-reminder listing of available skills with descriptions | observed in-session |
  | codex-cli 0.147.0 | model-visible skills list + `skills.list`/`skills.read` tools | binary strings |

  This is why the catalogue needs no in-repo index: one would be a second, staler copy of what the runtime already injects. **Re-verify on a major harness upgrade** — if a harness ever stopped listing skills, roles would still say "you have a list of available skills" and agents would quietly stop loading them.

  **The listing is not guaranteed complete, and roles must not claim it is.** Codex budgets its listing and, over budget, truncates descriptions and omits skills outright, reporting the loss only in telemetry. A skill can also be absent because it is in the wrong layout for that harness, has unparseable frontmatter, or sits behind a dangling symlink. So roles state the observable fact (*you have a list*) rather than the mechanism, and instruct agents to report an expected-but-missing skill as drift; `doctor`'s discovery check exists to answer why.

  Consequently `description` quality is a hard gate here and the catalogue stays small — those are the only two levers on discovery that actually exist.

## Versioning

One semver line drives all consumers. Claude Code re-fetches only when `plugin.json`'s `version` changes, so **every PR that touches `skills/`, `agents/`, `pi-agents/`, `roles/`, or `templates/` bumps the version in the PR itself** (usually the patch; set minor/major explicitly when warranted) — enforced by the `version-bump` check in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml). On merge, [`.github/workflows/release.yml`](../.github/workflows/release.yml) tags the merged version — tag-only; it pushes nothing to `main`. Keep `plugin.json` == `package.json` == git tag `vX.Y.Z`. **Claude Code** tracks `main` (always latest); **pi.dev** and **Codex** pin the tag (reproducible) — bump the pin to update.

## CI gates

`validate` (manifests + schema-v2), `roles-rendered` (render drift + skill-ref resolution), `generated-current` (catalog freshness + templates parse), `version-bump` (on content change), plus the security floor (gitleaks, osv-scanner, dependency-review). This repo is a **supply-chain root** — its skills and agents load as instructions into every consumer's agents; every change requires owner review.
