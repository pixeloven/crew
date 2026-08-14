---
name: platform-glossary
description: The platform's shared vocabulary — the resolved meaning of the ambiguous nouns every consumer reuses (app, surface, consumer, tenant, gateway, platform, workload, deployment/service, component, project, skill, MCP server vs MCP consumer) plus the three-level naming hierarchy (platform / deployment / K8s-primitive). Load when naming a thing, reasoning about where a workload lives, or before writing docs or manifests that use these terms. Generic; a consumer's concrete names live in its own local architecture skill.
tier: concept
requires: []
audience: [crew]
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
| **skill** | a loadable capability doc (`skills/<name>/SKILL.md`). A **platform skill** is generic and lives in the foundation; a **local skill** holds a consumer's specifics and lives in that consumer's overlay, **shadowing** the platform skill of the same name. |
| **MCP server** vs **MCP consumer** | an **MCP server** *exposes* tools / resources over MCP (the provider being called). An **MCP consumer** (client) is a runtime that *connects to and calls* an MCP server — typically a surface. Name which side you mean; "MCP client" alone hides it. |

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

This skill holds only the generic nouns and the hierarchy. A consumer's **local architecture skill** binds them to reality: its actual surfaces, the canonical name of each workload (Application ⇄ namespace), which namespaces are isolation tenants, and which of its things is the LLM/MCP gateway versus the ingress gateway. Where a consumer's local skill and this one disagree for that consumer, the **local skill wins** and the discrepancy is fixed upstream here. For the generic app-of-apps mechanics that these nouns describe, see `argocd-deployment-patterns`.
