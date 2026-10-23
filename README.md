# Crew

Crew is PixelOven's portable agent foundation: one methodology-skill catalogue,
seven shared role definitions, and an audit-first onboarding contract for Claude
Code, pi.dev, and OpenAI Codex.

| Harness | Foundation skills | Crew roles | Project behavior |
|---|---|---|---|
| Claude Code | plugin | seven rendered `agents/*.md` roles | root `AGENTS.md` through `CLAUDE.md` |
| pi.dev | git package | seven rendered `pi-agents/*.md` roles, dispatched as `crew.<role>` | root `AGENTS.md` |
| OpenAI Codex | plugin or vendored `.agents/skills` | uses Codex dispatch; plugin roles are unsupported | root `AGENTS.md` |

The same `skills/<name>/SKILL.md` tree feeds every harness. Claude and Pi roles
are rendered from one neutral `roles/<role>/role.yml` + `body.md` source, so names,
descriptions, body text, and intended posture stay aligned.

## Scope

Crew contains portable agent methodology. Stack conventions live in packs (see
[Packs](#packs)). Project topology,
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
requires and disappear silently. From `v0.39.0`, Crew on Pi requires
`pi-subagents` `>=0.62.0` for its `excludeTools` posture. On Pi, roles register
as `crew.<role>`. Dispatch the qualified name: a bare `reviewer` or `researcher`
resolves to pi-subagents' own built-ins. On every harness, MCP side effects are
governed by role behaviour, not by the `writes:` posture.

- [Claude Code quickstart](docs/quickstart-claude-code.md)
- [pi.dev quickstart](docs/quickstart-pi.md)
- [OpenAI Codex quickstart](docs/quickstart-codex.md)

One identity, three spellings: the repo is `pixeloven/crew`, the package is
`@pixeloven/crew`, and the plugin is `crew@pixeloven`. Nothing is published to a
package registry — releases are git tags.

Claude Code and Codex install the plugin from the shared catalogue at
[`pixeloven/marketplace`](https://github.com/pixeloven/marketplace), which pins
this repo by commit SHA; this repo carries no marketplace of its own. Pi has no
marketplace concept and installs the package from a `vX.Y.Z` tag directly.

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

## Packs

Domain, stack, and craft skills belong in **packs**: sibling `<domain>-skills`
plugins that ship skills only, may fill Crew's slots with `provides:`, declare
`plugin:crew@>=X.Y.Z` in every skill's `requires:`, and run Crew's own checks —
in CI, one job:

```yaml
jobs:
  crew:
    uses: pixeloven/crew/.github/workflows/pack-checks.yml@vX.Y.Z
```

A local overlay still outranks a pack. See [Packs](docs/PACKS.md) for the
contract, the required README sections, and moving a skill out of Crew. Skills
name capabilities (`mcp:tracker`, `cli:gh`), never products, and degrade when one
is missing; [Capabilities](docs/CAPABILITIES.md) lists the shared names and how
an agent adapts.

### Removed after 0.49.1: `character-and-worldbuilding`

No Crew role used `character-and-worldbuilding`, so it no longer ships with
Crew. It is parked in [crew#109](https://github.com/pixeloven/crew/issues/109),
which keeps the full skill text and plans a creative skills pack where it will
return. A project that relies on it can keep a local copy until then.

### Migrating to 0.44.0: stack skills moved to `infra-skills`

`terraform-conventions`, `ansible-conventions`, `k8s-kustomize-conventions`,
`k8s-workload-patterns`, and `github-actions-conventions` no longer ship with
Crew. They live in the [`infra-skills`](https://github.com/pixeloven/infra-skills)
pack (`infra-skills@pixeloven`). To keep them:

1. install `infra-skills` beside Crew on each harness;
2. on Claude Code and Codex, change every `crew:<skill>` reference in `AGENTS.md`,
   local skills, and role overlays to `infra-skills:<skill>`. Pi's flat namespace
   keeps the bare name.

Crew Doctor reports any remaining reference to a moved skill as `DEGRADED`, and
an Onboarding audit proposes each rename. `mcp-server-design` and
`python-conventions` stay in Crew.

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

Both read one inventory. `scripts/crew_inventory.py` is a read-only engine: it
lists installed plugins and skill roots, MCP servers as configured, CLIs on
`PATH`, and filled and empty slots. It writes nothing and prints to stdout.

```sh
python3 /absolute/resolved/crew/root/scripts/crew_inventory.py --project /absolute/consumer/repo --format gaps
```

Onboarding writes the inventory into the `agent-runtime` slot as a `## Capabilities`
table that maps each capability to its provider and a fallback command. Doctor's
`inventory.capability-map` row reports a table that differs on this machine. MCP
records carry a server's name, transport, scope and command basename only, never
its env, headers, args or URL. MCP tool lists are visible only inside a session, so
the agent pipes what it sees with `--observations -`. The
[Maintainers](docs/MAINTAINERS.md) page dates what each harness exposes.

Ask an agent to “learn `gh` for this project” (or any CLI, MCP server or vendor
tool) and the `learn` skill reads the inventory's gaps, gathers the tool's own
help, schemas and repository usage as untrusted evidence, and drafts one proposal
per lesson into the queue the project's `AGENTS.md` declares — report-only when it
declares none. The proposal must pass `learn_contract.py --check` and an
adversarial `reviewer` pass, and only the operator promotes it. See
[Learning](docs/LEARNING.md) for the contract.

## Maintenance

One semver line drives the package and plugin manifests. Edit role sources rather
than rendered files, run the full fixture and render gates, and never publish from
an implementation branch. See [Maintainers](docs/MAINTAINERS.md) for repository
layout, generation, and validation commands.
