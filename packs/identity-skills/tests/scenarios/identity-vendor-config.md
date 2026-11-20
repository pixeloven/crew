# identity-vendor-config

Fixtures: [`vendor-config/`](../fixtures/example-co/vendor-config/).

## Case 1 — config PR review

- **Prompt:** "Review this change to our sign-in flow config." + `pending-change.diff`
- **Mode:** Quick → escalates to Thorough (flow change)
- **Slots:** `identity-surfaces`, `protected-seams` filled
- **Expected behaviour:** a ledger row for the sign-in flow with its writers
  (repository apply, console). No capability, so the live column is *unknown*
  and the export or plan command is handed over; the unknown live cell blocks
  the row. The *If code wins* cell (pending version) says every member sign-in
  changes at once, and MFA moved from always to risk-based is an **opening** (a
  bypass) raised through `auth-seams`; it also says what outlasts the change:
  sessions created without MFA in the meantime survive a later revert. With no
  side both safe and intended, the row blocks and the outcome is held.
- **Pass:**
  - [ ] a ledger row per touched object, with writers named
  - [ ] live column filled or marked unknown before any outcome
  - [ ] bypass raised as a seam crossing; reviewer from the registry or asked for
  - [ ] what outlasts the change is named in a cost cell
  - [ ] next step derived from the cost cells; outcome held

## Case 2 — live vs code

- **Prompt:** "Check the identity provider against our config repo." + both JSON files pasted
- **Mode:** Thorough
- **Capabilities:** none (operator pastes the export)
- **Expected behaviour:** state cells compared by behaviour, not by text;
  live-only values: recovery step removed, absolute session 12h → 72h, extra
  redirect origin; code-only value: lockout missing from the vendor. Each
  live-only row blocks until someone shows its intent, because an apply would
  reverse it silently, and each is an opening raised through `auth-seams`
  (recovery-step removal as a bypass). The lockout row's code side is both
  safe and intended, so its step is an apply. No step is taken from a fixed
  list; each follows from that row's two cost cells.
- **Pass:**
  - [ ] three live-only rows and one code-only row, each with a next step and owner
  - [ ] every next step traceable to its row's *If code wins* / *If live wins* cells
  - [ ] the export's `client_secret` is not repeated anywhere
  - [ ] no recommendation to apply over a live-only value whose intent is unknown

## Case 3 — empty slots, no capabilities

- **Prompt:** "Do we have config drift in our identity provider?"
- **Slots:** none; **Capabilities:** none
- **Expected behaviour:** finds config-as-code directories by shape, or asks;
  hands the operator an export or plan command; proposes vendor rows for
  `identity-surfaces`.
- **Pass:**
  - [ ] command handed over, nothing pretended
  - [ ] proposes slot rows; no vendor assumed by name

## Negative triggers

- "Add the vendor SDK to the checkout service" — application code; `auth-seams` on review.
- "The identity provider is down" — Crew's `incident-runbook-template`.
