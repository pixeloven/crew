---
name: ansible-conventions
description: Use when writing, changing or reviewing Ansible roles, playbooks, or inventory. Covers repository structure, runtime secret injection, Jinja2/bash delimiter traps, boot-only hardware services, and idempotent check-mode runs.
tier: subject
requires: [plugin:crew@>=0.38.0]
expects-local: [platform-conventions, secret-paths, topology]
---

## SSH and inventory

All managed hosts use the project's standard `ansible_user` from its platform-conventions local skill, if it defines one — not root. That user has SSH key authentication and passwordless sudo.

Inventory lives at `ansible/inventory/`. Host definitions cover every host Ansible manages — hypervisor nodes, standalone VMs — per the project's topology local skill.

## Secret injection

Secrets are never stored on disk. Inject them at runtime with a wrapper that resolves references when the playbook starts. The shape is the same whatever the backend — a committed file of *references*, resolved into env vars for one invocation:

```bash
<secret-runner> --env-file=ansible/<refs>.env -- ansible-playbook playbooks/<playbook>.yml
```

The env file holds references only (secret-manager URIs or paths), never values. Password-manager CLIs, `sops exec-env`, and vault agents all fit this pattern; which one the project uses, and its reference paths, belong in the project's secret-paths local skill, if it defines one. Never hardcode credentials in playbooks, vars files, or inventory. Where encrypted-at-rest vars are unavoidable, use `ansible-vault` and keep the vault password out of the repo.

## Role structure

Roles live under `ansible/roles/` — one role per host responsibility, not one per task. A role owns everything for its host class. Example layout:

| Role | Purpose |
|---|---|
| `<management-vm>/` | Standalone management VM configuration (e.g. container runtime, reverse proxy, auth stack) |
| `<hypervisor>_power/` | Host power tuning (e.g. CPU governor, GPU power services) |

The project's concrete role inventory lives in its platform-conventions local skill, if it defines one.

## Boot-only hardware services — critical gotcha

Some systemd services manipulate hardware in ways that are only safe at boot (example: a GPU idle-power service that unbinds GPUs from their current drivers to set minimum power limits). **Never use `state: started` or `state: restarted`** on such services — starting one while the hardware is in use (e.g. a VM holding the GPU) can hang or crash the host.

Correct usage — enable without starting:
```yaml
- name: Enable <boot-only-service>
  ansible.builtin.systemd:
    name: <boot-only-service>
    enabled: true
    daemon_reload: true
  # No 'state:' key — boot-only service, never started by Ansible
```

Which of the project's services are boot-only is recorded in its platform-conventions local skill, if it defines one.

## Jinja2 / bash template conflict

Bash array syntax `${#array[@]}` conflicts with Jinja2's comment tag `{# ... #}`. In templates that mix bash and Jinja2, add this header:

```
#jinja2: comment_start_string:'{##', comment_end_string:'##}'
```

This remaps Jinja2's comment delimiters so `{#` is treated as literal bash.

## Non-Kubernetes services

Some services deliberately live outside any cluster on Ansible-managed hosts (e.g. a small utility container on a management VM). Manage them via their host's role — never assume every service is a Kubernetes workload. The project's topology local skill, if it defines one, records which services live where.

## Idempotency

All playbooks and roles must be safe to run repeatedly. Test with `--check --diff` before applying to production hosts. Use `changed_when: false` for commands that are inherently read-only but trigger changed state in Ansible's model.

## Review checks

- [ ] No secrets in playbooks, vars files, templates, or inventory; secrets are injected at runtime through a reference file and the project's secret runner (its secret-paths local skill names which)
- [ ] `ansible_user` matches the project's inventory convention, not root
- [ ] Boot-only services are enabled without a `state:` key; no task starts or restarts one
- [ ] Templates that mix bash and Jinja2 carry the comment-delimiter remap header
- [ ] Read-only commands set `changed_when: false`
- [ ] The playbook is idempotent: a second run, and a `--check --diff` run, report no changes
