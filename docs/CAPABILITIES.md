# Capabilities

A **capability** is a kind of source or tool a skill can use: an issue tracker, a
data warehouse, the GitHub CLI. Skills name the capability, never the product, so
one skill works in any organisation. Each organisation says which tool answers
each name. Skills adapt to the organisation; they never encode one.

A name has one of four forms:

| Form | Means |
|---|---|
| `mcp:<group>` | A kind of source an agent reaches through a tool connection, usually an MCP server: a tracker, a wiki, a warehouse. |
| `cli:<tool>` | A command-line binary on `PATH`, named by its executable. This form is open: any binary may be named. |
| `external:<x>` | A remote service reached directly: `github` or `web`. |
| `cluster` | Access to the project's running infrastructure. |

## Where a capability appears

1. **`requires:` in frontmatter: a hard need, and rare.** List a capability only
   if the skill's guidance means nothing without it. A pack skill's `requires:`
   should normally be `[plugin:crew@>=X.Y.Z]` alone.
2. **Skill bodies and `crew:discoverable` markers: a soft need, and preferred.**
   A body says "if the tracker (`mcp:tracker`) is available, read the fields
   from it"; a stub section marked `<!-- crew:discoverable capability=mcp:tracker -->`
   tells Onboarding that `learn` can draft the section from that source (see
   [Packs](PACKS.md#marking-stub-sections)).
3. **The capability map: what this machine and organisation actually have.**
   The `## Capabilities` table in the project's `agent-runtime` fill has one row
   per capability: its provider, kind, state, and the fallback command the
   operator wrote. Onboarding generates it from `scripts/crew_inventory.py`, and
   Doctor reports when it differs on this machine.

## Vocabulary

Only names a skill uses, or clearly will, are listed. The providers are examples,
not endorsements; any tool that answers the same question can provide the name.

| Name | Means | Typical providers | Used by |
|---|---|---|---|
| `mcp:tracker` | Issue or work tracker: items, fields, states, links | Jira, Linear, GitHub Issues, Azure Boards, Shortcut | planning-skills (`readiness-gates`, `tracker-sync`, stubs) |
| `mcp:docs` | Docs, wiki or knowledge base: specs, PRDs, runbooks | Confluence, Notion, Google Docs, GitBook, a docs repo | planning-skills (`requirements-review`, `prd-bar` stub) |
| `mcp:warehouse` | SQL data warehouse: tables, schemas, queries | Snowflake, BigQuery, Redshift, Databricks, Postgres | identity-skills (`auth-funnel-signatures`, `identity-event-schema` stub) |
| `mcp:analytics` | Product analytics: events, funnels, cohorts | Amplitude, Mixpanel, PostHog, Heap, GA4 | identity-skills (`auth-funnel-signatures`, `identity-event-schema` stub) |
| `mcp:logs` | Log search and observability: logs, traces, errors | Datadog, Grafana Loki, Elastic, Splunk, CloudWatch | identity-skills (`auth-flow-tracing`, `auth-funnel-signatures`) |
| `cli:gh` | The GitHub CLI | `gh` | crew (`release-and-versioning`), identity-skills |
| `cli:git` | Git | `git` | any skill that reads history or branches |
| `external:github` | GitHub itself: repos, PRs, Actions, releases | github.com, GitHub Enterprise | crew (five skills), identity-skills, infra-skills |
| `external:web` | The public web: vendor docs, standards, advisories | web search or fetch tools | open research steps |
| `cluster` | The project's running infrastructure | Kubernetes, Nomad, ECS, a VM fleet | infrastructure and incident work |

The machine-readable list is [`capabilities.txt`](capabilities.txt); a test keeps it
and this table in step. `check_skills.py` warns, without failing, on an `mcp:` name
in `requires:` or a `crew:discoverable` marker that is not listed. The inventory
marks a gap on an unlisted `mcp:` or `external:` name the same way.

## How an agent adapts

A missing or differently shaped capability is normal. It is never a reason to fail.

**(a) Present: use it.** Read the capability map, use the provider it names, and
record in the output which source each fact came from.

**(b) Absent: degrade, don't fail.** Fall back in this order, and stop at the
first step that works:

1. another listed capability that answers the same question (the warehouse often
   holds the analytics events; `cli:gh` covers much of `external:github`);
2. ask the operator to run a command or query you provide (the map's Fallback
   cell, or one you write) and paste the result back;
3. proceed on method alone: give the steps and the queries to run, say what is
   missing, and lower the stated confidence.

**(c) A different shape: map the meaning, not the provider.** The capability
might arrive by another route: analytics events queried through the warehouse, the
tracker through a CLI rather than an MCP server, or a custom internal tool. The
capability map's row names the actual provider, and the skill keeps using the
capability's *meaning*. When no row maps it, `learn` drafts the map row, or a local
tool skill, as a proposal; only the operator promotes it.

**(d) Never invent.** Do not assume a provider, a server name, a table, an event
or a field the map or the tool itself has not shown you. An unknown stays unknown
and is reported.

**(e) Report the sources.** Every report says which capabilities were used, with
their providers, and which were missing and what that cost.

## Adding a name

- **Reuse before adding.** If an existing name answers the same question, use it,
  even when the product differs: Jira and Linear are both `mcp:tracker`. Add a
  name only for a new kind of question, such as team messaging (`mcp:chat`) once
  a skill needs one.
- **Naming.** Use kebab-case, and name a kind of source, never a product or vendor:
  `mcp:warehouse`, not `mcp:snowflake`. `cli:` names the binary, because the binary
  is the interface.
- **Process.** Open a PR to Crew that adds the name to this table and to
  `capabilities.txt` together, with the skill or stub that needs it. Until it
  merges, a pack may use the new name; the check warns rather than fails.
