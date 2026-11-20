# Example Co — identity event schema (fixture fill)

## Event catalogue

| Step | Event name | Store | Key fields |
|---|---|---|---|
| 1 | `session_started` | warehouse `auth_events` | `session_id`, `platform`, `ts` |
| 2 | `identifier_submitted` | warehouse `auth_events` | `session_id`, `account_id` |
| 3 | `challenge_issued` | warehouse `auth_events` | `session_id`, `challenge_kind` |
| 4 | `challenge_passed` | warehouse `auth_events` | `session_id`, `challenge_kind` |
| 5 | `session_established` | warehouse `auth_events` | `session_id`, `account_id` |
| side | `recovery_started`, `contact_changed` | warehouse `auth_events` | `account_id` |

## Identifiers

`account_id` (opaque, use in output) ↔ `idp_subject` (vendor) via
`account_links`. Contact addresses live in `accounts.email`, restricted.

## Signal reliability

| Signal | Store | Coverage | Latency | Blind spots | Validated against | Use | Measured |
|---|---|---|---|---|---|---|---|
| funnel step ratios | `auth_events` | all sessions | under 1 hour | none known | release-log replays | rely | 2026-09-30 |
| `device_class_new` | `auth_events` | about 60% of sign-ins | under 1 hour | absent before an account's first sign-in | 40 closed investigations | corroborate | 2026-09-30 |
| `vendor_risk_score` | `auth_events` | all sign-ins | under 1 hour | one value for >99% of rows | none | cite only | 2026-03-01 |
| `geo_region_change` | — | not emitted | — | — | — | cite only | 2026-09-30 |

Review interval: 90 days.

## Signal families

| Family | Evidenced by | Signals |
|---|---|---|
| challenge flooding | challenges issued per session with no pass | funnel step ratios |
| recovery hijack | recovery or contact change, then a new session | funnel step ratios, `device_class_new` |

## Restricted fields

`accounts.email`, `accounts.phone`, `auth_events.client_ip` — filter or
aggregate only, never select.

## Change and experiment log

Pointer: the release log at `telemetry/change-log.csv` (fixture stand-in);
readable by anyone on the identity team.

## Query templates

```sql
-- funnel by week, normalised to session start
SELECT week, step, COUNT(DISTINCT session_id) * 1.0
       / NULLIF(SUM(CASE WHEN step = 'session_started' THEN 1 END) OVER (PARTITION BY week), 0) AS rate
FROM auth_events WHERE ts >= :start AND ts < :end GROUP BY week, step;
```
