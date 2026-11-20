# auth-flow-tracing

## Case 1 — session lost between services

- **Prompt:** "Members get bounced back to login after paying at checkout. Trace what happens to their session."
- **Mode:** Thorough (failure)
- **Slots:** `identity-surfaces`, `protected-seams` filled
- **Capabilities:** none (working tree only)
- **Expected behaviour:** one identity (the member's session) and one decision
  point (where the member is sent back to login) named first; walks backwards
  through `checkout-auth-middleware` and `auth-api` token validation to where
  the member signed in; each step's arrives as / proven by / vouched for by /
  leaves as / lost or added; seams marked; brackets the break between the last
  intact and first wrong step, with candidate causes (audience mismatch, cookie
  domain, expiry) labelled fact or inference; asks the operator for an
  aggregate log search it cannot run itself.
- **Pass:**
  - [ ] decision point and origin both named
  - [ ] chain-of-custody table present, decision point first, every column filled or marked unknown
  - [ ] break bracketed as last intact / first wrong
  - [ ] every weak link and cause labelled fact or inference
  - [ ] handed-over log search uses opaque IDs and no token value
  - [ ] sources used / missing listed

## Case 2 — design understanding

- **Prompt:** "Explain how a partner-portal request is authorised end to end, for the design review."
- **Mode:** Quick
- **Expected behaviour:** chain of custody from the authorisation decision back to
  sign-in, unconfirmed steps flagged, no break analysis.
- **Pass:**
  - [ ] does not pad with breaks nobody asked for
  - [ ] unconfirmed steps explicitly marked

## Case 3 — empty slots

- **Prompt:** "Trace our SSO login across the gateway and the vendor."
- **Slots:** none; **Capabilities:** none
- **Expected behaviour:** discovers steps from code and config; records the
  vendor callback and claim mapping as steps in the chain; names steps it could
  not confirm and what would reach them; no invented owners.
- **Pass:**
  - [ ] vendor callback present as a step
  - [ ] no owner invented
  - [ ] proposes `identity-surfaces` rows for steps discovered

## Negative triggers

- "Why is this pod crash-looping?" — Crew's `incident-runbook-template`, not tracing.
- "Draw our service architecture" — not an auth flow.
