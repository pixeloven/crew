---
name: platform-glossary
description: The platform's shared vocabulary — the resolved meaning of the ambiguous nouns every consumer reuses (app, surface, consumer, tenant, gateway, platform, workload, deployment/service, component, project, skill, MCP server vs MCP consumer) plus the three-level naming hierarchy (platform / deployment / K8s-primitive) plus two human-vs-machine traps — "the operator" always means the human, and "crew" means this foundation's roles rather than a firstmate-lineage tool's dispatched workers. Load when naming a thing, reasoning about where a workload lives, or before writing docs or manifests that use these terms. Generic; a consumer's concrete names live in its own local architecture skill.
tier: concept
requires: []
---

The generic vocabulary every consumer of the platform shares. Terminology drift is load-bearing: "app", "gateway", "agent", and "project" each carry several distinct meanings, and conflating them silently corrupts design discussions and manifests alike. This skill is the one place the ambiguous nouns resolve. It is **generic** — a consumer specializes it with concrete names (its actual services, namespaces, gateway hosts) in its own **local architecture skill**, which shadows this one where the two disagree for that consumer.

## The resolved nouns

Bare use of an ambiguous term below is banned in favour of the qualified form.

| Term | Resolution |
|---|---|
| **platform** | the shared foundation itself — the reusable agent fleet + skill catalog that many consumers build on. Not any one deployment. |
| **consumer** | the actor or project that *uses* the platform (a person, or a project's deployment). A consumer supplies its own local skills for its specifics. A consumer is **not** a tenant and **not** a surface. |
| **surface** | the collective noun for the **agent runtimes** — the runtime entry points where an agent actually runs and is reached (a web chat UI, a worker runtime, a conversational agent runtime, an editor CLI). "client" is banned for this sense. |
| **tenant** | a **hard-isolation boundary** for untrusted or CI-supplied code (e.g. ephemeral CI runners). A tenant is an isolation domain; a consumer is a trusted user of the platform. Never call a consumer a tenant. |
| **gateway** | banned bare — always qualify. **LLM/MCP gateway** = the model-and-tool federation front door (virtual keys, MCP access groups). **ingress gateway** = the cluster's HTTP entry (ingress controller / reverse proxy). A conversational agent runtime is a *surface*, never a "gateway". |
| **app** | banned bare — three distinct senses: the ArgoCD **`Application` kind** (the registration object) · the deployed **workload** (the running thing) · the literal **`apps/` directory** (where a base lives). Say which. |
| **workload** | the deployed unit the GitOps controller manages as **one Application** — the default noun for "a deployed thing". |
| **deployment** / **service** | Capitalized = the **K8s kind only** (`Deployment`, `Service`). Lowercase "deployment" in a topology / registration context is ambiguous → prefer **workload**. |
| **component** | reserved for a shared manifest **base** under `base/{component}/` — a reusable base composed by an aggregator overlay. Not a synonym for workload or service. |
| **project** | banned bare — the ArgoCD **`AppProject`** (an RBAC / allow-list boundary) · the **consumer project** (the actor / repo that consumes the platform) · a **repo**. Say which. |
| **skill** | a loadable capability doc (`skills/<name>/SKILL.md`). A **platform skill** is generic and lives in the foundation; a **local skill** holds a consumer's specifics and lives in that consumer's overlay, **shadowing** the platform skill of the same name (in a flat namespace such as pi's; Claude Code namespaces the plugin copy as `plugin:skill`, so there both stay visible). |
| **MCP server** vs **MCP consumer** | an **MCP server** *exposes* tools / resources over MCP (the provider being called). An **MCP consumer** (client) is a runtime that *connects to and calls* an MCP server — typically a surface. Name which side you mean; "MCP client" alone hides it. |
| **the operator** | **the human being who directs the work** — the person an agent escalates to, asks for a decision, or reports to. This is the default and winning reading of the phrase in every agent contract, prompt, plan, and doc. A *tool* named "operator" is written in code style (`operator`); see below. |
| **crew** | banned bare when both senses are in play — the foundation's **crew roles** (lead, implementer, reviewer, triage, …) versus an external tool's **crew of dispatched workers**. Say "crew role" or name the tool's vocabulary explicitly; see below. |

### "the operator" is a person, not a program

Escalation instructions across the fleet say things like *"ask the operator"*, *"the operator approves"*, *"escalate to the operator"*. **These always mean a human.** An agent that reads them as naming a program will do something plausible and wrong, which is the worst failure shape available.

A component may still be *named* operator. The rule that keeps both usable:

- **Prose keeps "the operator" for the human.** Unqualified, unhedged, no disambiguation at each use — the existing corpus stays correct by default.
- **A project called operator is always code-styled** (`operator`) and never capitalized as a proper noun. Capitalization is invisible at the start of a sentence — exactly where *"The operator should…"* appears — so it cannot carry the distinction.
- Where a sentence would still be ambiguous, say "the `operator` project" or "the `operator` repo". Never "Operator".

Kubernetes "operators" (controllers that reconcile a custom resource) are a third sense. They are usually disambiguated by their neighbouring nouns (CRD, controller, reconcile); qualify when they are not.

### "crew" — the foundation's roles vs. an external tool's workers

Two vocabularies use *crew* for different things, and both appear in this fleet's working context:

| Vocabulary | "crew" means | The human is | A worker is |
|---|---|---|---|
| **this foundation** (harmony-crew) | the **set of agent roles** — lead, implementer, reviewer, researcher, triage, investigator, responder | **the operator** | a dispatched **role**, e.g. "a reviewer" |
| **firstmate lineage** (`kunchenguid/firstmate` and its forks, e.g. `pixeloven/operator`) | the **fleet of dispatched worker agents** in a running session | **the captain** | a **crewmate** (or a **secondmate** — a persistent worker with its own isolated home) |

Rules:

- **Never translate between them silently.** A firstmate *crewmate* is a running process in a git worktree; a foundation *crew role* is a declarative capability definition. They are not the same kind of thing and one does not implement the other.
- Use the tool's own word when talking about that tool ("spawn a crewmate", "the captain approves the merge"), and this foundation's word when talking about roles ("dispatch the reviewer").
- **"the captain" and "the operator" denote the same human** in a session that spans both. Do not introduce a third name for that person.
- In our own prose, prefer **"crew role"** over bare "crew" whenever a firstmate-lineage tool is anywhere in scope.

### "agent" is overloaded — always qualify

"agent" spans at least three roles depending on context: a **crew role** (lead, implementer, reviewer, …), a **surface** (the runtime an agent runs in), and a **conversational persona** (a companion). A namespace or service whose name contains "agent" almost always needs disambiguation — a consumer resolves its own "agent"-named things in its local architecture skill. Never assume two "agent…" names denote the same role.

## The three-level naming hierarchy

A thing carries (up to) three names, one per level. Keep them aligned unless a documented exception applies; a mismatch between levels is a common source of the confusion above.

| Level | What names it | Portable? |
|---|---|---|
| **Platform (conceptual)** | this glossary's vocabulary — *surface*, *workload*, *consumer*, *gateway* | yes — same across every consumer |
| **Deployment** | the ArgoCD **Application name** + the **namespace name** (these should match) | no — one consumer's chosen names |
| **K8s primitive** | the in-cluster object names — `Deployment`, `Service`, `PVC`, ingress objects | no — the running objects |

Read a name by its level: a platform-level word (*surface*) names a *role*; a deployment-level word names *one consumer's* Application / namespace; a primitive-level word names a *running object*. When someone says "the X app", resolve which level they mean before acting.

## How a consumer specializes this

This skill holds only the generic nouns and the hierarchy. A consumer's **local architecture skill** binds them to reality: its actual surfaces, the canonical name of each workload (Application ⇄ namespace), which namespaces are isolation tenants, and which of its things is the LLM/MCP gateway versus the ingress gateway. Where a consumer's local skill and this one disagree for that consumer, the **local skill wins** and the discrepancy is fixed upstream here. For the generic app-of-apps mechanics that these nouns describe, see the project's GitOps-deployment local skill.
