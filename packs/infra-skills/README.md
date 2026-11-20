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

| Harness | How | Notes |
|---|---|---|
| Claude Code | plugin `infra-skills@pixeloven` | from `pixeloven/marketplace` |
| pi.dev | git package `git:github.com/pixeloven/infra-skills@vX.Y.Z` | add beside Crew in `packages` |
| OpenAI Codex | plugin `infra-skills@pixeloven`, or vendor `skills/` into `.agents/skills/` | from `pixeloven/marketplace` |

One identity, three spellings: the repo is `pixeloven/infra-skills`, the
package is `@pixeloven/infra-skills`, and the plugin is `infra-skills@pixeloven`.
Nothing is published to a package registry — releases are git tags.

Claude Code and Codex install the plugin from the shared catalogue at
[`pixeloven/marketplace`](https://github.com/pixeloven/marketplace), which pins
this repo by commit SHA, the same way it pins Crew. Codex reads the same
`.claude-plugin/plugin.json` `"skills": "./skills"` declaration Crew uses; there
is no separate Codex manifest. For a local checkout, `claude --plugin-dir
/absolute/path/to/infra-skills` works too.

Install the pack at user scope, beside Crew, so it is available machine-wide
in every session. Install Crew (`crew@pixeloven`) first, then:

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

Follow Crew's quickstarts; this pack adds skills, not setup. As with Crew,
Claude Code and Codex namespace plugin skills
(`infra-skills:<name>`) while project skills stay bare, so a same-named local
skill does not shadow the pack copy. Do not rely on collision behaviour to
disable a pack skill.

## Description cost

Measured with Crew's `check_skills.py --pack --report-cost` at Crew v0.45.0:

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

Run Crew's checks from the installed Crew root, by absolute path:

```sh
CREW=/absolute/resolved/crew/root
python3 "$CREW/scripts/check_skills.py" --pack --root /absolute/path/to/infra-skills --report-cost
python3 "$CREW/scripts/check_skill_layout.py" /absolute/path/to/infra-skills
```

CI calls Crew's reusable `pack-checks.yml` workflow (see `.github/workflows/ci.yml`).

## Versioning

`.claude-plugin/plugin.json` and `package.json` carry the same version, and the
release tag is `vX.Y.Z` of that version. Bump it in any change that touches
`skills/`; Claude Code re-fetches a plugin only when its version changes.

## License

MIT — see [LICENSE](LICENSE).
