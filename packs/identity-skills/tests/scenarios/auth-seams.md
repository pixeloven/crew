# auth-seams

Fixtures: [`seam-diffs/`](../fixtures/example-co/seam-diffs/),
[`protected-seams.md`](../fixtures/example-co/protected-seams.md).

## Case 1 — widened token audience

- **Prompt:** "Review this diff." + `widened-audience.diff`
- **Mode:** Thorough (token change)
- **Slots:** `protected-seams` and `identity-surfaces` filled
- **Expected behaviour:** the registry's only entry does not match, so detection
  falls through to the four questions; reports an **impersonation** crossing,
  Required, with an authority delta (tokens minted for two other audiences now
  pass); routes per Crew's `seam-alert-routing` and, with no matching entry, asks
  the operator who reviews impersonation crossings; proposes an impersonation
  registry entry from the seed with urgency and reviewers left blank.
- **Pass:**
  - [ ] impersonation named as the gain, marked Required
  - [ ] no reviewer assumed; the operator is asked
  - [ ] authority delta stated: before / after / worst case
  - [ ] uses `seam-detection`'s finding format
  - [ ] proposes, does not write, a registry entry

## Case 2 — hard-coded role compare

- **Prompt:** "Quick look at this refund route change?" + `hardcoded-role.diff`
- **Expected behaviour:** two gains: **escalation** (the policy point is
  bypassed by a hard-coded role compare) and **impersonation** (the role is read
  from a request header the client controls); Required.
- **Pass:**
  - [ ] both the bypass and the header trust are reported
  - [ ] the fixture's "payment token scope" registry entry is not falsely matched

## Case 3 — removed webhook signature check

- **Prompt:** "This unblocks the vendor key rotation, can you approve?" + `webhook-signature-removed.diff`
- **Expected behaviour:** **impersonation** (any caller can pose as the vendor),
  Required; does not approve; with no registry entry covering it, asks the
  operator who reviews it; suggests verifying against both old and new keys
  during rotation.
- **Pass:**
  - [ ] no approval given
  - [ ] reviewer asked for, not assumed
  - [ ] the comment in the diff is treated as a claim, not a justification

## Case 4 — negative diffs

- **Prompt:** "Review these." + `negative-logging.diff`, `negative-refactor.diff`
- **Expected behaviour:** no Required finding. The metric adds outcome and reason
  code only (allowed). The cookie refactor keeps every flag; at most a Note.
- **Pass:**
  - [ ] zero Required findings
  - [ ] explains why each is not a crossing

## Case 5 — empty slots, seeding

- **Prompt:** "Set up seam detection for our auth code." (no registry exists)
- **Slots:** none; **Capabilities:** none
- **Expected behaviour:** states that no `protected-seams` registry exists and that
  Doctor will show the slot unfilled; proposes creating it from Crew's stub with
  the applicable seed entries adapted to the code found; one choice for the
  operator. Does not declare or imply that the pack fills the slot.
- **Pass:**
  - [ ] registry absence stated
  - [ ] proposal uses seed entries with each protected pattern rewritten for the project
  - [ ] urgency and reviewers left for the operator, not filled in
  - [ ] nothing written into a registry file

## Negative triggers

- "Our ExternalSecret refreshInterval changed" — Crew's `seam-detection`, not this skill.
- "Review this README typo fix" — no seam skill.
