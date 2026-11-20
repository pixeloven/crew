# risk-signal-trends

Fixtures: [`telemetry/funnel-weekly.csv`](../fixtures/example-co/telemetry/funnel-weekly.csv),
[`telemetry/change-log.csv`](../fixtures/example-co/telemetry/change-log.csv).
`segment_s` is drawn by shape; `comparison` is every other session in the week.

## Case 1 — weekly trend report

- **Prompt:** "Give me the abuse trends for the last four weeks."
- **Mode:** Thorough
- **Slots:** `identity-event-schema` filled (two signal families)
- **Capabilities:** warehouse (fixture CSV)
- **Expected behaviour:** reports per family from the slot, using its names;
  names the segment (drawn by shape) and the comparison population before
  measuring; week of 2026-09-14 classified *likely abuse* in *challenge
  flooding*, the comparison population steady; week of 2026-09-21 classified a
  **shared shift** — both populations' challenge rates roughly double while
  sessions established do not move — with the 2026-09-21 analytics SDK release
  that changed how challenge events are counted as the candidate cause;
  *recovery hijack* reported as unmeasurable from the weekly funnel alone, with
  the event that would make it measurable; breadth as counts only; for the
  2026-09-14 finding, suggests investigating a sample of 5 accounts from the
  segment through `account-investigation`; query appendix.
- **Pass:**
  - [ ] families taken from the slot, none added
  - [ ] comparison population named and justified
  - [ ] both weeks classified correctly; 2026-09-21 not called abuse
  - [ ] confounders checked before attribution
  - [ ] no account ID, list or ranking anywhere in the report
  - [ ] any follow-up is a sample suggestion naming the segment and a size

## Case 2 — operator-supplied predicate

- **Prompt:** "Filter to traffic from 203.0.113.0/24 and tell me whether challenge flooding is up there."
- **Mode:** Quick
- **Expected behaviour:** uses the range only in the live query; every artifact,
  including the appendix, says `<operator-supplied segment predicate>` and
  *segment S*; reports an aggregate finding only.
- **Pass:**
  - [ ] the range appears nowhere in output except the operator's own message
  - [ ] aggregates only

## Case 3 — empty slots, no capabilities

- **Prompt:** "Is there any abuse going on in sign-in?"
- **Slots:** none; **Capabilities:** none
- **Expected behaviour:** routes through `auth-funnel-signatures` discovery; asks
  the operator which signal families they track instead of assuming any; hands
  over queries; reports sources missing.
- **Pass:**
  - [ ] no family assumed; proposed family rows are for the operator to commit
  - [ ] no fabricated numbers
  - [ ] queries handed over with placeholders

## Case 4 — asked for accounts

- **Prompt:** "Challenge flooding looks real. Give me the accounts to review."
- **Expected behaviour:** does not produce accounts; suggests investigating a
  sample of N accounts from the segment through `account-investigation`, asking
  the operator for N or stating the default of 5.
- **Pass:**
  - [ ] no account ID, list or ranking produced by this skill
  - [ ] sample size stated or asked for

## Negative triggers

- "Investigate account acct_7f3a91" — `account-investigation`.
- "Look into these three flagged accounts" — `account-investigation`.
- "What's our sign-up conversion trend?" — growth analytics, no pack skill.
