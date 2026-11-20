---
name: identity-surface-map
description: Use when asked where identity lives, who owns an auth service or integration, or when scoping or routing identity work across services, shared code and vendor config. Maps surfaces by facts and the organisation's own dimensions, and proposes the identity-surfaces registry.
tier: concept
requires: [plugin:crew@>=0.45.0]
expects-local: [identity-surfaces]
---

# Identity surface map

Find where authentication, authorization, sessions and identity data live, record
the same facts about each place, and keep the project's registry honest. Where the
project has an `identity-surfaces` local skill, start from it and treat it as the
record of truth; this skill's job is then to confirm it and find what it misses.
With the slot empty, discover from scratch and propose its first content.

## Facts, then the organisation's dimensions

Organisations divide identity work differently, so this skill ships **no fixed
classes**. It records facts any organisation can sort by, then applies whatever
dimensions the organisation defines.

**Facts, for every surface:**

- **Location** and its **kind**: application code, deploy or gateway config, or a
  vendor tenant (and, for a tenant, whether its config is held as code).
- **Ships changes** — the team that merges and deploys a change to it. Not who
  wrote it first.
- **Touches identity by** — the mechanism: issues tokens, validates tokens
  itself, calls a shared library, trusts a header or claim from an upstream
  service, hands the user to a vendor-hosted page, evaluates policy, stores
  identity data.
  One line, in the code's own terms.
- **Owner** — the accountable team or role, and the path-ownership rule (a
  CODEOWNERS entry or equivalent) that enforces it, if any.

**Dimensions** come from the slot. The `identity-surfaces` fill may define any
number of them — the sensitivity of the data a surface holds, how often it
changes, regulatory scope, anything — each with its allowed values and what each
value means for review and routing. Apply each defined dimension to every
surface. With none defined, do not invent one: report the facts, and offer the
operator a draft dimension drawn from what you found (for example, the kinds of
identity data the surfaces store, or how often each one shipped a change last
quarter), with values in their words.

## Discovery

Use whatever the project's `agent-runtime` capability map says is available.
Record each source you used and each you could not reach.

1. **Repositories.** Search the code you can read for identity vocabulary: token
   verification, session creation, policy-check calls, claim names, webhook
   signature checks, identity library imports, CODEOWNERS entries naming an
   identity team. With `external:github` or `cli:gh`, widen to the
   organisation's other repositories; without it, list the searches for the
   operator to run.
2. **Deploy and gateway config.** Routes that require authentication, auth
   filters, service-to-service credentials by **reference only**.
3. **Vendor config.** Directories of identity-provider flows, policies or roles
   held as code. If a vendor's admin API is in the capability map, list its
   configured objects by name only; never read tenant secrets.
4. **People.** Ask the operator which surfaces they know of that you missed. A
   surface no one can name an owner for is a finding, not a gap to fill by guess.

Every surface is a *logical name, a location and an owner*. Never record a
hostname with credentials, a tenant secret, or a personal identifier.

## Edge cases

- Code one team wrote and another now ships: record who ships it.
- A vendor feature configured only in a console: a vendor-tenant location, *not
  held as code* — itself a finding for `identity-vendor-config`.
- A shared library is one surface; a caller is a surface of its own only where it
  adds identity logic beyond the call.
- Generated clients and test helpers are not surfaces.

## Output

A table in the `identity-surfaces` stub's shape, then the evidence:

```markdown
## Identity surfaces — <scope> (<date>)

| Surface | Location | Kind | Ships changes | Touches identity by | Owner | <one column per defined dimension> | Evidence |
|---|---|---|---|---|---|---|---|

### Findings
- <surface with no owner / vendor config not held as code / registry row with no code / surface no dimension value fits>

### Sources
- used: <capabilities and searches run>
- missing: <what would have widened the search, and how to add it — `learn`>

### Proposed slot change
<diff against the project's identity-surfaces fill, or a new fill from the stub>
```

The proposed slot change is for the operator to commit. Do not write into the
slot yourself. If the gap is a tool you could not use, point at Crew's `learn`.

## Depth

| Mode | When | Output |
|---|---|---|
| Quick | one question ("who owns sign-in?") or a single repository | the rows that answer it, sources |
| Thorough | an empty slot, or a cross-organisation scope | full table, findings, proposed slot fill |
| Critique | an existing registry | rows with no code behind them, code with no row, stale owners, dimension values nobody uses |

## Routing work

Route by what the slot's dimensions say each value means. Where they say
nothing, route by the facts: the work goes to the team that **ships changes**;
add an identity reviewer when the mechanism is one `auth-seams` guards; a
vendor-tenant location goes through `identity-vendor-config`. A change spanning
several surfaces is a candidate for `auth-flow-tracing` before it is planned.
