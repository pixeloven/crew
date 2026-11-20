---
name: <project>-identity-event-schema
description: <Project>'s identity event schema — auth events in funnel order, where each field is stored, identifier mappings, signal reliability, the signal families tracked, restricted fields, query templates, and the change/experiment log pointer. Load before querying auth telemetry or investigating accounts.
---

This file is the **output of discovery**, not a prerequisite. The pack's
`auth-funnel-signatures`, `account-investigation` and `risk-signal-trends` skills
work with it empty: they find what they can through the capabilities in the
project's `agent-runtime` map, or hand the operator queries to run, and propose
the rows below for you to commit.

**Never put secrets, credentials, personal data, or attack indicators here.** No
sample rows, no real identifiers, no addresses, no values seen during an
investigation. Field and table names, data types and reliability judgements
only. Where a restricted system holds sensitive material, record a pointer to it
and who can open it, never its contents.

## Event catalogue

<!-- crew:discoverable capability=mcp:warehouse -->
<!-- crew:discoverable capability=mcp:analytics -->

> **▸ Fill:** the auth events in funnel order (session start → identifier entered →
> challenge issued → challenge passed → session established, or whatever your
> flows actually emit), with the store that holds each one.
>
> | Step | Event name | Store | Key fields | Notes |
> |---|---|---|---|---|
> | 1 | `<event>` | `<warehouse table / analytics project / log index>` | `<field names>` | `<gaps, sampling>` |

## Identifiers

<!-- crew:discoverable capability=mcp:warehouse -->

> **▸ Fill:** each identifier kind (internal user ID, vendor subject ID, session ID,
> device ID, anonymous ID), which stores carry it, and how they map to each other.
> Name the **opaque** ID agents should use in durable output. Contact addresses
> are lookup keys only: resolve them to an opaque ID inside the query.

## Data flow

> **▸ Fill:** how events move from the emitting surface to each store, with
> typical latency and any sampling or retention limit. A short arrow list is
> enough.

## Signal reliability

<!-- crew:discoverable capability=mcp:warehouse -->

> **▸ Fill:** one row per signal an investigation might lean on, with what was
> measured and the **use** it earns: **rely**, **corroborate** (never the only
> evidence) or **cite only**. Missing is unknown, never `false`.
>
> | Signal | Store | Coverage | Latency | Blind spots | Validated against | Use | Measured |
> |---|---|---|---|---|---|---|---|
> | `<signal>` | `<store>` | `<share of relevant events, and where lower>` | `<event to store>` | `<when it is wrong by construction>` | `<ground truth used, or none>` | rely / corroborate / cite only | `YYYY-MM-DD` |
>
> Your review interval: `<e.g. 90 days>`. Rows older than it are **stale** and
> re-measured before use.

## Signal families

> **▸ Fill:** the abuse patterns your organisation tracks, in your own words. One
> row per family: the funnel steps or shapes that evidence it and the signals
> that count toward it. List only families you actually watch; add one when you
> start watching it.
>
> | Family | Evidenced by | Signals |
> |---|---|---|
> | `<your name for it>` | `<steps or shape>` | `<signal names from the table above>` |

## Restricted fields

> **▸ Fill:** the fields agents may filter or aggregate on but must never select
> into output (addresses, names, phone numbers, network addresses tied to a person,
> payment data), and the redaction each needs.

## Change and experiment log

> **▸ Fill:** a **pointer** to where auth-affecting deploys, flag flips and
> experiments are recorded (a release log, a flag service's audit view, an
> experiment registry), and which capability can read it. Investigations overlay
> it before attributing a spike to an attacker. A pointer, not a copy.

## Query templates

<!-- crew:discoverable capability=mcp:warehouse -->

> **▸ Fill:** parameterised templates in your store's dialect for the funnel by
> period, the funnel for one opaque account ID, and the identifier resolution
> lookup. Placeholders only — never a literal value.
