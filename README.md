# Crew

Crew is PixelOven's portable agent foundation: one methodology-skill catalogue,
seven shared role definitions, and an audit-first onboarding contract for Claude
Code, pi.dev, and OpenAI Codex.

| Harness | Foundation skills | Crew roles | Project behavior |
|---|---|---|---|
| Claude Code | plugin | seven rendered `agents/*.md` roles | root `AGENTS.md` through `CLAUDE.md` |
| pi.dev | git package or `--skill` | seven rendered `pi-agents/*.md` roles as readable files; Crew dispatches nothing on pi | root `AGENTS.md` |
| OpenAI Codex | plugin or vendored `.agents/skills` | uses Codex dispatch; plugin roles are unsupported | root `AGENTS.md` |

The same `skills/<name>/SKILL.md` tree feeds every harness. Claude and Pi roles
are rendered from one neutral `roles/<role>/role.yml` + `body.md` source, so names,
descriptions, body text, and intended posture stay aligned.

## Scope

Crew contains portable agent methodology. Stack conventions live in packs (see
[Packs](#packs)). Project topology,
credentials, access maps, protected seams, runtime contracts, and decision-record
formats belong in the
consumer's local `.agents/skills/` overlay. The installed catalogue's
`expects-local:` declarations identify the six currently required concern slots,
each with a starter stub in `templates/local-skills/`.

Each skill description is the model-visible discovery interface. CI requires
discriminating trigger language first and enforces a documented 110–300 character
policy. The maximum is a conservative repository contract derived from observed
catalogue pressure, not a permanent product byte limit.

## Install

Use the harness quickstart and a published `vX.Y.Z` tag. On pi, Crew provides
its skills and ships its roles as readable files (`pi-agents/*.md`); it
registers no agents and no tools. Orchestration on pi belongs to a supervising
host such as [operator](https://github.com/pixeloven/operator), not to Crew.
Since 0.62.0 Crew no longer ships the experimental `crew_agent` pi extension or
declares pi-subagents (see the [CHANGELOG](CHANGELOG.md)).
On every harness, MCP side effects are governed by role behaviour, not by the
`writes:` posture.

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

**Enable packs per project by default.** Every listed skill's description is paid
in every session. Enable a pack only in the projects that use it, and keep user
scope for a pack every project needs. Enabling only the packs a project uses saves
29–53% of the always-on listing cost of Crew and its packs, with no trigger cost
for the packs that stay. Each quickstart ([Claude Code](docs/quickstart-claude-code.md#enable-packs-per-project),
[Codex](docs/quickstart-codex.md#enable-packs-per-project),
[pi.dev](docs/quickstart-pi.md#enable-packs-per-project)) shows the project-scope
form. Since 0.55.0, Doctor predicts when Claude Code would list skills by name
only and recommends project scope for packs enabled user-wide.

### Migrating to 0.52.0: estate- and stack-specific material moved out

Crew core now keeps only portable practice. What moved:

| Was in Crew | Now in |
|---|---|
| `crew:python-conventions` | `language-skills:python-conventions` ([`language-skills`](https://github.com/pixeloven/language-skills)) |
| `crew:pr-review-checklist` Kubernetes, secret-sync, Terraform and Ansible checks | the "Review checks" in `infra-skills:k8s-kustomize-conventions`, `infra-skills:k8s-workload-patterns`, `infra-skills:terraform-conventions` and `infra-skills:ansible-conventions` |
| `crew:seam-detection` secret, scheduling, LLM-gateway access and RBAC seams | `infra-skills:infra-seams`, which seeds them into your `protected-seams` registry |
| `crew:incident-runbook-template` Kubernetes sweep sections and diagnostic commands | `infra-skills:k8s-diagnostics` |
| Implementer's uv, kubectl and Terraform validation commands | the Validation section of each stack's conventions skill |

`seam-detection` keeps the method, a product-free list of common shapes, the
agent-runtime seam and the finding format. `incident-runbook-template` keeps the
incident report, issue conventions and a sweep skeleton with one section per
component your `topology` names. `pr-review-checklist` keeps the universal checks
and points at each touched stack's conventions skill. Install `infra-skills` and
`language-skills` beside Crew to keep the stack material, and rename
`crew:python-conventions` to `language-skills:python-conventions` (Pi keeps the
bare name). Doctor and Onboarding report and propose that rename.

**Removed slot names: `litellm-access-map` and `vault-ops`.** Both were specific
to one platform, so Crew no longer names them: their stubs under
`templates/local-skills/` are gone and they are no longer accepted in
`expects-local:`. Keep your own local skills for those concerns and the
`AGENTS.md` rows that point at them; just drop the two names from any
`expects-local:` list.

The `LICENSE` copyright holder is now PixelOven.

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
an Onboarding audit proposes each rename. `mcp-server-design` stays in Crew;
`python-conventions` moved later, in 0.52.0.

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

Since 0.54.0, Crew also runs under a supervising host: a fleet tool, CI job or
scheduler. When the task contract a session was given defines delegation, review,
delivery, reporting, decision records, external writes or knowledge capture, that
contract wins over roles and skills. Unattended, an agent records the decision it
needs in the channel the host names and stops instead of waiting. Whether a
session is hosted is a property of that session, not a repository setting. A
host that reserves `AGENTS.md` for humans selects Onboarding's `hosted` audit
profile, which reports
without proposing entry-file merges (`--audit-profile hosted`); the host's task
contract says whether apply is available.

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

Ask it to “learn from this session”, or let `plan-validation`'s closing retro hand
it the plan's signals, and `learn` drafts the same proposals from experience:
operator corrections, repeated failures, tool denials, reviewer findings and
Doctor drift. A behaviour lesson needs two separate incidents, each with its own
evidence. Every lesson with a diff carries a fixture that replays the original
failure; `learn_contract.py --eval-case` renders a skill lesson's fixture as a
`claude plugin eval` case, which the operator runs before promoting it.

## Maintenance

One semver line drives the package and plugin manifests. Edit role sources rather
than rendered files, run the full fixture and render gates, and never publish from
an implementation branch. See [Maintainers](docs/MAINTAINERS.md) for repository
layout, generation, and validation commands.
