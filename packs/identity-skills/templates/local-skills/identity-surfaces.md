---
name: <project>-identity-surfaces
description: Registry of <Project>'s identity surfaces — where authentication, authorization, sessions and identity data live, who ships and owns each, how it touches identity, and the dimensions <Project> classifies them by. Load when scoping, routing or tracing identity work.
---

This registry is the **output of discovery**, not a prerequisite. The pack's
`identity-surface-map` skill proposes rows from what it finds in the
repositories, deploy config and vendor config it can reach; you review and commit
them. Every pack skill still works while this file is empty.

**Never put secrets, credentials, personal data, or attack indicators here.** This
file loads into agent context and is committed to the repository. It holds logical
names, paths and owners, nothing a person or an attacker could be identified by.
Point at a restricted system rather than copying from it.

## Dimensions

> **▸ Fill:** the ways *you* classify identity surfaces, if any. Zero dimensions
> is a valid answer; the skills then route by the facts in the table. For each
> dimension: its name, its allowed values, and what each value means for who
> reviews or does the work.
>
> | Dimension | Values | What each value means |
> |---|---|---|
> | `<your name>` | `<value>`, `<value>` | `<who reviews, who is told, which skill applies>` |

## Surfaces

<!-- crew:discoverable capability=external:github -->

> **▸ Fill:** one row per surface, plus one column per dimension above. Keep
> names logical (`login-service`, `admin-policy-config`), not hostnames or
> account IDs.
>
> | Surface | Location | Kind | Ships changes | Touches identity by | Owner | Path ownership |
> |---|---|---|---|---|---|---|
> | `<logical name>` | `<repo>/<path>` or `<vendor tenant label>` | code / deploy config / vendor tenant (as code? yes / no) | `<team that merges and deploys>` | `<mechanism, one line>` | `<team or role>` | `<CODEOWNERS path or equivalent>` |

## Vendors

> **▸ Fill:** each identity vendor by **role** (identity provider, customer
> identity platform, policy engine, risk scoring), the surfaces configured in it,
> whether its config is held as code and where, and which capability in the
> project's `agent-runtime` map can read its state, if any. No tenant secrets.

## Change and ownership

> **▸ Fill:** who approves new rows and new dimensions, and how stale rows are
> found (for example: a quarterly re-run of `identity-surface-map` in Critique
> mode).
