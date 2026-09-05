---
name: doctor
description: Health-check this project's agent-foundation install and report what actually works — package present, roles resolvable, which capabilities this session can genuinely reach, unfilled local-skill slots, whether a local copy is silently shadowing a plugin one, and whether every skill on disk actually loaded into this runtime. Load when asked to run the doctor, verify or debug the install, check onboarding status, diagnose a skill that seems to be ignored or missing, or answer "what can I actually reach here".
tier: concept
requires: []
---

# Doctor

Run the checks below in order, then produce the report. Absence of a platform is a **profile**, not a failure — this skill never treats "no cluster, no gateway" as an error; it records what's reachable and recommends the matching posture. The foundation itself needs nothing but a repo.

## The checks

**1. Installation.**
- Claude Code: `.claude/settings.json` (project or user) has the `crew` marketplace + `enabledPlugins` entry. pi.dev: `.pi/settings.json` packages include `harmony-crew` (note the pinned tag — report if it lags the installed catalog's version). OpenAI Codex: the catalog is present in the repo's `.agents/skills/` or `~/.agents/skills/` (report which, and the pinned tag if recorded), and `config.toml` has an `mcp_servers` entry for the LiteLLM gateway with a `bearer_token_env_var`.
- The seven roles resolve: the harness's agent list contains `lead`, `triage`, `investigator`, `researcher`, `responder`, `reviewer`, `implementer` (or the `role-*` pi variants). If skills load but agents don't (or vice versa), the install is partial — say which half. On **Codex**, the foundation does not yet render `.codex/agents/*.toml`, so report the roles as *not yet rendered for this harness* (a known gap, not a broken install) and confirm instead that the `AGENTS.md` routing table is present — that table is what triggers Codex's delegation.

**2. Entry file.**
- A repo-root `AGENTS.md` exists. Claude Code repos also want a `CLAUDE.md` containing `@AGENTS.md`.
- It is *behavioral*: short, with the routing table, and no fact-stuffing (infra tables, credential paths, command catalogs). If facts have accreted, recommend re-running `onboarding`.
- The ▸ Fill blocks are actually filled (ask-list, verification commands, local-skills map, tripwires) — an unfilled template is a half-onboarded project.

**3. Capability probe.** The foundation's own skills need only `external:github` — check `gh auth status`. Beyond that, probe whatever **the project's local skills** declare they need: if the overlay ships knowledge-base, gateway, or cluster skills, confirm the corresponding tools are actually in this session's tool list and say which are reachable. Present = granted; absent = not granted, which is a fact to report rather than an error.

**3b. Plugin install state — three registries that disagree.** Claude Code keeps the
answer in three places and only one is what a session loads:

    known_marketplaces.json   what the marketplace last served
    settings.json             what is ENABLED
    installed_plugins.json    what a session ACTUALLY loads

`marketplace update` refreshes the first and leaves the third pointing at the old
version — so `plugin details` reports the new one while sessions get the old one.
Report all three, and flag any disagreement. Note the record reconciles only on
the NEXT session start: mid-reinstall a session reports zero skills, which looks
like a break and is not.

**3c. Scope.** A capability applied to THE WORK belongs at user scope; knowledge
about a SPECIFIC ARTIFACT FORMAT belongs to the project. Flag anything registered
at both — duplicate registration is how one stale version gets three entries — and
anything universal declared in a project file.

**3d. Description budget.** Descriptions are always-on; bodies are not. Report the
total description bytes, because Codex caps its listing (~21.5 KB) and past that
truncates EVERY description rather than dropping a skill — the discovery mechanism
degrades catalogue-wide while everything still appears present. `claude --plugin-dir
<path> plugin details <name>` gives real per-component token cost.

**4. Local slots.** For each slot the installed skills declare in `expects-local:` (`platform-conventions`, `topology`, `protected-seams`, `litellm-access-map`, `secret-paths`, `vault-ops`, `agent-runtime`): does the project's overlay (`.agents/skills/`, `.claude/skills/`) or its `AGENTS.md` local-skills map name a skill filling it? Only flag slots that matter for the project's profile — a portable-profile repo doesn't need `topology`. Starter stubs: the foundation's `templates/local-skills/`.

**5. Intake prerequisites** (only if the project routes work through Triage): `gh label list` shows the `domain:*` labels (and `agent:queued` / `triage:needs-clarification` if used). Missing labels mean Triage's routing silently no-ops.

**6. Shadowing** — the check that catches silent staleness. In pi's flat namespace a project-level skill **overrides** the plugin's version of the same name. Claude Code namespaces plugin skills as `plugin:skill`, so there the two coexist under different names rather than shadowing — a stale local copy hides in plain sight instead of winning outright. List any collisions and say which copy wins, because a stale local copy makes foundation updates invisible with no error. If a local copy is an old snapshot rather than a deliberate override, that's the finding.

**7. Discovery — does the runtime see every skill on disk?** This is the check nothing else can do, because it compares what the harness *actually loaded* against what exists.

Agents find skills because the harness lists them, with their descriptions, before the first turn. That listing is the discovery mechanism — so a skill the runtime didn't load is invisible no matter how correctly it sits on disk, and nothing errors.

- **What you see.** Your own context already holds the list — the skills available to you, each with its description. That is the authoritative side of this comparison; read it from what you were given, not from a file. On Codex, `skills.list` returns the same set on demand.
**Verify by running a session, never by reading a registry.** Every registry above
lied at some point in a real diagnosis: the marketplace said 0.29.0, the record said
0.25.0, the settings said enabled, and the session loaded nothing. `claude -p` in a
separate process is the only answer that counts — skills load at session start, so a
session cannot observe its own change.

- **Use the harnesses' own tools first** — they are maintained alongside the
  runtimes that read these files, and they see things no external check can:

      claude plugin validate <path> --strict          manifests, frontmatter, and
                                                      the rule that plugin
                                                      components are read WITHOUT
                                                      following symlinks
      claude --plugin-dir <path> plugin details <n>   component inventory and
                                                      projected token cost
      codex debug prompt-input "hi"                   the model-visible skill
                                                      listing, no API call

  Then `scripts/check_skill_layout.py <repo-root>` for what they miss: verified
  that `plugin validate --strict` PASSES both a flat `skills/<name>.md` and a
  `name:` disagreeing with its directory — the two faults that actually shipped.
  It takes a path, and `--selftest` proves it can still fail. Only then read
  trees by hand.
- **What's on disk.** Enumerate the overlay directories — `.agents/skills/*/SKILL.md` (pi and Codex) and `.claude/skills/*/SKILL.md` (Claude Code, usually symlinks into the former) — plus the installed foundation catalogue. A flat `.claude/skills/*.md` is a **finding, not a layout**: report every one.
- **Report the difference in both directions.** On disk but not loaded is the serious one: name each and give the likely cause — wrong layout — **every harness wants `<name>/SKILL.md` directories**, and a flat `.claude/skills/<name>.md` is invisible to Claude Code with no error — or unparseable YAML frontmatter, a dangling symlink, or a `name:` that disagrees with the directory name. Loaded but not on disk means it came from a different install path — say which.
- **Codex only:** its skills listing is **budgeted**. Over budget, it truncates descriptions and omits skills entirely, and it counts what it dropped (`omitted_skills`, `truncated_skill_descriptions`). If skills are missing from your listing on Codex, suspect the budget before suspecting the files, and report catalogue size as the cause — the fix is fewer or tighter skills, not a bigger index.

A count matching on both sides is the pass condition. Say the number.

## The report

A table — one row per check: **check | status (OK / MISSING / DEGRADED / N/A) | evidence | next action**. Then two closing lines:

- **Profile:** `portable` (the foundation's catalogue alone — its skills need nothing but a repo and, for a few, GitHub) or `platform` (the project's overlay adds capability skills whose tools this session can reach — name which). This is the input `onboarding` uses to tailor its recommendations.
- **Top action:** the single highest-leverage fix (or "healthy — nothing to do").

Keep it honest: report what you *verified*, not what config files claim. A tool listed but never probed is "present", not "working".
