---
name: k8s-diagnostics
description: Use when running a Kubernetes health sweep or diagnosing a failing node, pod, GitOps sync or secret sync. Gives kubectl, GitOps-controller and secret-sync checks per sweep section; node-OS tooling defers to topology.
tier: subject
requires: [plugin:crew@>=0.38.0]
expects-local: [topology, platform-conventions, agent-runtime]
---

Crew's `incident-runbook-template` owns the shape of the output: the incident
report, the issue conventions, and the sweep skeleton of one section per
component. This skill fills the Kubernetes sections of that sweep and gives the
commands behind each one. Which clusters, nodes, controllers and secret stores
exist is the project's `topology`; what "healthy" means for each (required
tolerations, expected sync settings) is its `platform-conventions`.

Everything here is read-only. A sweep or diagnosis never deletes, restarts,
syncs or patches; recommend the action in the report instead.

## Reaching the cluster

These checks need `cluster` access, usually through `cli:kubectl` with the
project's context. Read the capability map (the `## Capabilities` table in the
`agent-runtime` local skill) to see what this session has, and confirm the
context before any command:

```bash
kubectl config current-context
```

A GitOps controller may be reachable through a tool connection (an MCP server)
as well as its CLI. Use the provider the capability map names; when it names
none, use the CLI; when neither is present, give the operator the command to
run and paste back, and lower the stated confidence. Never guess a server or
tool name the map does not show.

## Sweep sections

Run one section per component the project's `topology` names. For a cluster
those are usually:

### Nodes

```bash
kubectl get nodes -o wide
kubectl describe node <node>        # Conditions, taints, allocatable vs allocated
kubectl top nodes                   # needs metrics-server
```

Report every node not `Ready`, and any `MemoryPressure`, `DiskPressure` or
`PIDPressure` condition. A taint the project does not expect is a finding.

### Pods

```bash
kubectl get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
kubectl get pods -A | grep -Ev 'Running|Completed'    # also catches CrashLoopBackOff, which is phase Running
kubectl describe pod -n <ns> <pod>                    # Events: scheduling, image pull, probe failures
kubectl get events -n <ns> --sort-by=.lastTimestamp
```

A `Pending` pod is usually scheduling: compare its tolerations and node
selector with `platform-conventions` before anything else.

### Logs

```bash
kubectl logs -n <ns> <pod> -c <container>
kubectl logs -n <ns> <pod> -c <container> --previous   # the crashed container
kubectl logs -n <ns> deploy/<name> --since=1h
```

Quote the first error, not the last line; the last line of a crash loop is
often the shutdown that follows it.

### GitOps controller

Report each application's sync status and health. With Argo CD:

```bash
argocd app list
argocd app get <app>                # sync status, health, last operation
kubectl get applications -A         # the same, from the cluster's custom resources
```

With Flux:

```bash
flux get kustomizations -A
flux get helmreleases -A
kubectl get kustomizations.kustomize.toolkit.fluxcd.io -A
```

`OutOfSync` with healthy resources is drift, not an outage; `Degraded` or a
failed last operation is. Name the resource the controller blames.

### Secret sync

Report each sync object that has not synced. With External Secrets Operator:

```bash
kubectl get externalsecret -A
kubectl describe externalsecret -n <ns> <name>    # Status.Conditions: SecretSynced or SecretSyncedError
kubectl get clustersecretstore,secretstore -A     # the store itself may be the failure
```

Sealed Secrets and CSI secrets-store drivers report through their own resources
and controller logs. A pod stuck in `CreateContainerConfigError` is often a
missing secret: check the sync object before the workload.

### Node OS

Node-level checks (kernel logs, OS health, the container runtime) use whatever
tooling the node OS provides. Which OS that is, and its commands, belong to the
project's `topology`. Without one, stop at `kubectl describe node` and say the
node-OS check was not run.

## Diagnosing one failure

Work from the symptom toward the cause, one layer at a time, and stop when a
layer explains it:

1. **Workload:** pod status, events, logs (`--previous` for a crash).
2. **Config:** the secret or config map it reads, and whether it synced.
3. **Scheduling:** tolerations, selectors, resources against allocatable.
4. **Delivery:** the GitOps controller's view of the application.
5. **Node:** conditions, then node-OS tooling per `topology`.

Write the result in `incident-runbook-template`'s incident structure, with the
commands you ran and what each showed. A clean sweep still produces output.
