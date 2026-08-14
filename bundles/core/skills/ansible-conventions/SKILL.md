---
name: ansible-conventions
description: Ansible role structure, inventory conventions, secret injection via op.env, and known gotchas (Jinja2/bash comment-delimiter conflicts, boot-only hardware services). Load when writing or modifying Ansible roles, playbooks, or inventory.
tier: subject
requires: []
audience: [crew]
expects-local: [platform-conventions, topology]
---

## SSH and inventory

All managed hosts use the project's standard `ansible_user` (see its conventions local skill; e.g. Harmony uses `ansible_user: harmony`) — not root. That user has SSH key authentication and passwordless sudo.

Inventory lives at `ansible/inventory/`. Host definitions cover every host Ansible manages — hypervisor nodes, standalone VMs — per the project's topology.

## Secret injection

Secrets are never stored on disk. Inject at runtime via `op run`:

```bash
op run --env-file=ansible/op.env -- ansible-playbook playbooks/<playbook>.yml
```

`ansible/op.env` contains `op://` URI references — 1Password resolves them at invocation time. Never hardcode credentials in playbooks, vars files, or inventory.

## Role structure

Roles live under `ansible/roles/` — one role per host responsibility, not one per task. A role owns everything for its host class. Example layout:

| Role | Purpose |
|---|---|
| `<management-vm>/` | Standalone management VM configuration (e.g. Docker, reverse proxy, auth stack) |
| `<hypervisor>_power/` | Host power tuning (e.g. CPU governor, GPU power services) |

The project's concrete role inventory lives in its conventions local skill.

## Boot-only hardware services — critical gotcha

Some systemd services manipulate hardware in ways that are only safe at boot (example: a GPU idle-power service that unbinds GPUs from their current drivers to set minimum power limits). **Never use `state: started` or `state: restarted`** on such services — starting one while the hardware is in use (e.g. a VM holding the GPU) will hang or crash the host.

Correct usage — enable without starting:
```yaml
- name: Enable <boot-only-service>
  ansible.builtin.systemd:
    name: <boot-only-service>
    enabled: true
    daemon_reload: true
  # No 'state:' key — boot-only service, never started by Ansible
```

Which of the project's services are boot-only is recorded in its conventions local skill.

## Jinja2 / bash template conflict

Bash array syntax `${#array[@]}` conflicts with Jinja2's comment tag `{# ... #}`. In templates that mix bash and Jinja2, add this header:

```
#jinja2: comment_start_string:'{##', comment_end_string:'##}'
```

This remaps Jinja2's comment delimiters so `{#` is treated as literal bash.

## Non-Kubernetes services

Some services deliberately live outside the cluster on Ansible-managed hosts (e.g. a Wake-on-LAN container on a management VM). Manage them via their host's role — never assume every service is a Kubernetes workload. The project's topology local skill records which services live where.

## Idempotency

All playbooks and roles must be safe to run repeatedly. Test with `--check` before applying to production hosts. Use `changed_when: false` for commands that are inherently read-only but trigger changed state in Ansible's model.
