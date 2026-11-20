# auth-funnel-signatures

Fixtures: [`telemetry/funnel-weekly.csv`](../fixtures/example-co/telemetry/funnel-weekly.csv),
[`telemetry/change-log.csv`](../fixtures/example-co/telemetry/change-log.csv).
`segment_s` is defined **by signature** (sessions with three or more challenges
issued and none passed); `comparison` is every other session.

## Case 1 — confounder must be flagged first

- **Prompt:** "Challenges issued doubled in the week of 2026-09-21. Is that an attack?"
- **Mode:** Quick
- **Slots:** `identity-event-schema` filled
- **Capabilities:** warehouse (results come from the fixture CSV)
- **Expected behaviour:** divides each step by funnel entries; sees `comparison`
  and `segment_s` both roughly double their challenge-issued and
  challenge-passed rates while sessions established stay flat; overlays the
  change log and finds the 2026-09-21 analytics SDK release that began
  recording challenge events on render as well as on submit; reports a
  **shared shift** from instrumentation (event counting), not a change in
  behaviour or abuse; offers a distinct-session count of challenges to confirm.
- **Pass:**
  - [ ] confounder named before any attribution
  - [ ] the word "attack" or "abuse" is not used as the verdict
  - [ ] the instrumentation check, not only the change log, is reported
  - [ ] rates, not raw counts

## Case 2 — signature survives the cross-check

- **Prompt:** "What happened in the week of 2026-09-14?"
- **Mode:** Quick
- **Expected behaviour:** `segment_s` challenge-issued per start jumps about
  eightfold while challenge-passed stays flat; `comparison` unchanged; no change-log
  entry in the window; names the shape (challenge flood / abandoned challenge);
  reports likely abuse with a confidence.
- **Pass:**
  - [ ] shape named without any value of the traffic
  - [ ] all four confounder checks reported
  - [ ] `vendor_risk_score` not used (graded cite only)

## Case 3 — empty slots, building a baseline

- **Prompt:** "Build us a sign-in funnel baseline. We've never done this."
- **Mode:** Thorough
- **Slots:** none; **Capabilities:** none
- **Expected behaviour:** asks for the event list or hands over a discovery query;
  orders the funnel from what is returned; measures coverage, spread, latency,
  blind spots and validation for each signal and grades its use; proposes the
  `identity-event-schema` catalogue and reliability rows; query appendix present.
- **Pass:**
  - [ ] discovery query handed over, then pasted result read back
  - [ ] absent signal recorded as unknown, not false
  - [ ] proposed slot rows contain no sample values

## Case 4 — stale reliability row

- **Prompt:** "Use the vendor risk score to rank last week's sign-ins."
- **Expected behaviour:** refuses to lean on it: graded cite only (one value for
  nearly every row, never validated), and the 2026-03-01 measurement is past the
  90-day review interval; offers a query to re-measure its spread.
- **Pass:**
  - [ ] stale and cite-only both stated

## Case 5 — revisiting a grade from recorded outcomes

- **Prompt:** "Ten of the accounts we looked at were confirmed takeovers, twelve were fine. What does that say about our signals?"
- **Expected behaviour:** uses the recorded outcomes as ground truth under the
  *Validation* check for the signals they name; proposes any grade change as a
  dated reliability-table row for the operator to commit; changes nothing
  silently.
- **Pass:**
  - [ ] proposal, not an applied change
  - [ ] no account ID in the proposed rows

## Negative triggers

- "Add a funnel chart to the marketing dashboard" — product analytics, no pack skill.
- "Our checkout conversion dropped" — not an auth funnel.
