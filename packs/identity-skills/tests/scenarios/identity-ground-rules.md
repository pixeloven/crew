# identity-ground-rules

## Case 1 — design review before any code

- **Prompt:** "We're adding magic-link sign-in to Example Co. Here's the design doc — what should identity care about?"
- **Mode:** design walk (no artifact depth)
- **Slots:** `identity-surfaces` filled from fixtures
- **Capabilities:** none
- **Expected behaviour:** walks the non-negotiables against the design; flags
  recovery-equivalence of magic links (8), session revocation (7), token
  audience and expiry (2), fail-closed on link validation (4); asks for a
  security reviewer because 2, 4 and 8 are touched; names `auth-api` as the
  owning surface from the slot.
- **Pass:**
  - [ ] cites at least four non-negotiables by number or name
  - [ ] recommends a security reviewer and says why
  - [ ] names the owner from the slot, not a guess
  - [ ] does not load `auth-seams` diff detection (there is no diff)

## Case 2 — logging question

- **Prompt:** "Can I log the user's email on failed sign-ins to debug lockouts?"
- **Mode:** principle lookup
- **Slots:** any
- **Expected behaviour:** no; proposes an opaque account ID plus a reason code,
  and an aggregate count by reason; cites the canonical PII rule.
- **Pass:**
  - [ ] answers no, with the opaque-ID alternative
  - [ ] does not offer a hashed address as a safe substitute without saying it is still personal data

## Case 3 — empty slots

- **Prompt:** "Review this authorization design for our new admin console." (design text only)
- **Slots:** none; **Capabilities:** none
- **Expected behaviour:** applies principles 1–4 and 6 to the design; says the
  owning surface is unknown and offers `identity-surface-map`; does not
  invent an owner or service name.
- **Pass:**
  - [ ] no invented owner, team or service
  - [ ] offers surface map as the way to fill `identity-surfaces`

## Negative triggers

- "Explain how OAuth works" — a teaching request; no pack skill should claim it.
- "Review this PR" (a CSS-only diff) — Crew's `pr-review-checklist`, not this skill.
