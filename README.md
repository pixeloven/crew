# Crew

Crew is PixelOven's portable agent foundation: one methodology-skill catalogue,
seven shared role definitions, and an audit-first onboarding contract for Claude
Code, pi.dev, and OpenAI Codex.

| Harness | Foundation skills | Crew roles | Project behavior |
|---|---|---|---|
| Claude Code | plugin | seven rendered `agents/*.md` roles | root `AGENTS.md` through `CLAUDE.md` |
| pi.dev | git package | seven rendered `pi-agents/*.md` roles | root `AGENTS.md` |
| OpenAI Codex | plugin or vendored `.agents/skills` | uses Codex dispatch; plugin roles are unsupported | root `AGENTS.md` |

The same `skills/<name>/SKILL.md` tree feeds every harness. Claude and Pi roles
are rendered from one neutral `roles/<role>/role.yml` + `body.md` source, so names,
descriptions, body text, and intended posture stay aligned.

## Scope

Crew contains portable methodology and stack conventions. Project topology,
credentials, access maps, protected seams, and runtime contracts belong in the
consumer's local `.agents/skills/` overlay. The installed catalogue's
`expects-local:` declarations identify the five currently required concern slots;
`templates/local-skills/` also offers recommended vocabulary for common optional
concerns.

Each skill description is the model-visible discovery interface. CI requires
discriminating trigger language first and enforces a documented 110–300 character
policy. The maximum is a conservative repository contract derived from observed
catalogue pressure, not a permanent product byte limit.

## Install

Use the harness quickstart and a published `vX.Y.Z` tag. Pi pins must be
`v0.35.0` or newer: older Crew roles lack the identity frontmatter pi-subagents
requires and disappear silently.

- [Claude Code quickstart](docs/quickstart-claude-code.md)
- [pi.dev quickstart](docs/quickstart-pi.md)
- [OpenAI Codex quickstart](docs/quickstart-codex.md)

The npm compatibility identity remains `@ductiletoaster/harmony-crew`. It is not
renamed or dual-published by this repository change; the active git/plugin
identity is `pixeloven/crew` and `crew@crew`.

## Local overlays and collisions

Put canonical project skills in `.agents/skills/<name>/SKILL.md`. Symlink each
directory into `.claude/skills/<name>` when Claude must load it. Project roles
use `.claude/agents/*.md` and `.pi/agents/*.md`.

Pi has a flat skill namespace, so its nearest project entry wins on collision.
Claude and Codex namespace plugin skills as `crew:<name>` while project entries
remain bare; both copies coexist. Do not rely on collision behavior to disable a
foundation skill.

Run the distributed validator by absolute installed-package path so a consumer's
same-named script cannot intercept the check:

```sh
python3 /absolute/resolved/crew/root/scripts/check_skill_layout.py /absolute/consumer/repo
```

The validator parses YAML frontmatter, checks directory-form skills, and validates
consumer roles in `agents/`, `.claude/agents/`, and `.pi/agents/`.

## Doctor and Onboarding

Ask an agent to “run Crew Doctor” for a fully read-only report. Doctor separates
installation, enablement, resolved runtime, and capability grants; compares disk
and runtime in both directions for the current harness; labels untested evidence;
and never starts a billed model probe without explicit approval.

Ask an agent to “onboard this project” for a non-mutating audit. That plain request
does not edit files. Applying findings requires a distinct, explicit apply
authorization for the current run, and destructive movement is routed through the
host runtime's decision interface. That host verifies a fresh, non-persisted
current-invocation signal; Onboarding does not mint, authenticate, save, or reuse
authorization tokens. Onboarding preserves mature entry files,
safety tripwires, project delivery contracts, and runbook pointers, then defers
implementation delivery to the project's existing workflow.

## Maintenance

One semver line drives the package and plugin manifests. Edit role sources rather
than rendered files, run the full fixture and render gates, and never publish from
an implementation branch. See [Maintainers](docs/MAINTAINERS.md) for repository
layout, generation, and validation commands.
