# infra-skills

Infrastructure stack conventions for coding agents: Terraform, Ansible,
Kubernetes (Kustomize and workload patterns), and GitHub Actions, each with the
review checks for its stack; plus infrastructure seam detection, Kubernetes
health-sweep diagnostics, and a go-public review for GitHub repositories.

infra-skills is a **pack** for [Crew](https://github.com/pixeloven/crew): a
sibling plugin that ships skills only, no roles, and plugs into Crew's roles
through the harness's skill listing. It meets Crew's
[pack contract](https://github.com/pixeloven/crew/blob/main/docs/PACKS.md) and
is checked by Crew's own published gates. Every skill declares
`requires: [plugin:crew@>=0.38.0]`.

## Skills

| Skill | Use when |
|---|---|
| `terraform-conventions` | Writing or reviewing Terraform or OpenTofu: staged applies, provider pinning, variables, secrets at plan/apply time |
| `ansible-conventions` | Writing or changing Ansible roles, playbooks, or inventory: runtime secret injection, Jinja2/bash traps, boot-only services |
| `k8s-kustomize-conventions` | Writing Kubernetes manifests or Kustomize files: base/overlay structure, patches, validation, GitOps sync targets |
| `k8s-workload-patterns` | Choosing a workload type or sizing a pod: resources, probes, storage, security context, runtime class, exposure |
| `github-actions-conventions` | Writing or reviewing GitHub Actions workflows: pinning, secrets, `gh` CLI, uv Python jobs, gitleaks |
| `infra-seams` | A diff touches secret-sync objects, tolerations, storage classes, RBAC, or an LLM/tool gateway's access config: seam shapes, greps, registry seed entries |
| `k8s-diagnostics` | Running a Kubernetes health sweep or diagnosing a failing node, pod, GitOps sync or secret sync |
| `go-public-review` | Making a GitHub repository public, or reviewing one already public: content over all history and PR refs, branches and tags, docs, public CI, security policy, licence |

The conventions skills carry a **Review checks** list for their stack; a review
applies the list of each stack the diff touches.
`infra-seams` adds infrastructure shapes to Crew's `seam-detection` method, as
`auth-seams` does for identity, and seeds the project's `protected-seams`
registry from [its seed file](skills/infra-seams/seed-seams.md).
`k8s-diagnostics` fills the Kubernetes sections of the sweep that Crew's
`incident-runbook-template` structures.
`go-public-review` is a checklist of criteria C1–C6 with an audit method; it
pairs with `github-actions-conventions` for the public-CI criterion and never
applies repository settings itself.

No project context is baked in. Anything bound to one estate — which cloud or
hypervisor provider, which secrets backend, cluster topology, domains, storage
classes, node OS, which gateway or GitOps controller — is deferred to the
consumer's local skills through `expects-local:` slots (`platform-conventions`,
`secret-paths`, `topology`, `protected-seams`, `agent-runtime`). Crew's
`templates/local-skills/` has starter stubs for each. No skill here fills a
slot (`provides:`); these are conventions and methods, not estate facts.

## Install

This pack lives in Crew's repo, under
[`packs/infra-skills`](https://github.com/pixeloven/crew/tree/main/packs/infra-skills), and ships on Crew's release
line. Install Crew first and follow its quickstarts; this pack adds skills, not
setup.

| Harness | How |
|---|---|
| Claude Code | `claude plugin install infra-skills@pixeloven`, from the `pixeloven` marketplace (`pixeloven/crew`, pinned to a release tag) |
| OpenAI Codex | `codex plugin add infra-skills@pixeloven`, from the same marketplace |
| pi.dev | the Crew package `git:github.com/pixeloven/crew@vX.Y.Z` carries this pack; a `skills` filter such as `["skills/**", "packs/infra-skills/**"]` loads it beside Crew ([pi.dev quickstart](https://github.com/pixeloven/crew/blob/main/docs/quickstart-pi.md#enable-packs-per-project)) |

On Claude Code, install the pack at user scope, beside Crew, so it is available
machine-wide in every session:

```sh
claude plugin install infra-skills@pixeloven --scope user
```

User scope is the CLI default and writes
`"enabledPlugins": { "infra-skills@pixeloven": true }` to
`~/.claude/settings.json`. Each enabled pack adds its descriptions to the
always-on skill listing, and Claude Code collapses an over-budget listing to
names only, which hurts skill selection; the description cost below is the
price of keeping the pack on everywhere.

To enable the pack only in specific infrastructure repos instead, run
`claude plugin install infra-skills@pixeloven --scope project` from the project
root. This writes the same entry to the project's `.claude/settings.json`,
which you can also edit by hand and commit so the whole team gets it.
`--scope local` does the same in `.claude/settings.local.json` for you alone.
On pi.dev, the per-project form is an `autoload: false` delta on the Crew
package in the project's `.pi/settings.json` (same quickstart section). To try
a local checkout, run `claude --plugin-dir /absolute/path/to/crew/packs/infra-skills`.

The pack lives at `packs/infra-skills` in `pixeloven/crew` and installs as the
plugin `infra-skills@pixeloven`. Its `package.json` names it `@pixeloven/infra-skills`, but
it is not a pi package of its own: pi loads it through the Crew package. Before
Crew 0.67.0 the pack had its own repo,
[`pixeloven/infra-skills`](https://github.com/pixeloven/infra-skills); the fold imported it
at that repo's `main` head, and its earlier commit history stays there. The
plugin ID is unchanged. Nothing is published to a package registry — releases
are Crew's git tags.

As with Crew, Claude Code and Codex namespace plugin skills
(`infra-skills:<name>`) while project skills stay bare, so a same-named local skill
does not shadow the pack copy. Do not rely on collision behaviour to disable a
pack skill.

## Description cost

Measured with Crew's `check_skills.py --pack --report-cost` at Crew v0.67.0:

```text
ansible-conventions         224
github-actions-conventions  205
go-public-review            236
infra-seams                 213
k8s-diagnostics             216
k8s-kustomize-conventions   222
k8s-workload-patterns       207
terraform-conventions       218
total always-on description chars: 1741 (8 skills)
```

## Checks

Crew's CI checks this pack in its `packs` matrix job, with the scripts from the
same checkout. To run the same checks locally from a Crew checkout:

```sh
CREW=/absolute/path/to/crew
PACK="$CREW/packs/infra-skills"
python3 "$CREW/scripts/check_skills.py" --pack --root "$PACK" --report-cost
python3 "$CREW/scripts/check_skill_layout.py" "$PACK"
python3 "$CREW/scripts/check_links.py" "$PACK"
python3 "$CREW/scripts/check_versions.py" "$PACK"
```

## Versioning

This pack carries Crew's version: `.claude-plugin/plugin.json` and
`package.json` match Crew's, and Crew's `vX.Y.Z` tag releases them together
([Versioning](https://github.com/pixeloven/crew/blob/main/docs/MAINTAINERS.md#versioning)). Bump Crew's
version in any change that touches this pack; Claude Code re-fetches a plugin
only when its version changes. From 0.67.0 the release notes are in
[Crew's CHANGELOG](https://github.com/pixeloven/crew/blob/main/CHANGELOG.md). [CHANGELOG.md](CHANGELOG.md) here covers the pack's own releases up
to 0.3.0.

## License

MIT — see [LICENSE](LICENSE).
