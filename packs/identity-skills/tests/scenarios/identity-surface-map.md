# identity-surface-map

## Case 1 — who owns it

- **Prompt:** "Who owns the checkout auth middleware?"
- **Mode:** Quick
- **Slots:** `identity-surfaces` filled
- **Expected behaviour:** answers from the slot: the payments team ships and owns
  it; it holds `claims-only` data (it reads tokens validated by the shared
  library and stores no credentials); cites the row.
- **Pass:**
  - [ ] owner and shipping team correct
  - [ ] routing taken from the slot's own dimension, not a built-in category

## Case 2 — empty slots, discovery

- **Prompt:** "Where does identity live in our codebase? We've never written it down."
- **Mode:** Thorough
- **Slots:** none; **Capabilities:** none (only the working tree)
- **Expected behaviour:** searches the working tree for identity vocabulary;
  records the facts for each surface; applies no dimension, since none is
  defined, and offers a draft dimension for the operator to name; lists searches
  it could not run (other repositories, vendor admin) for the operator; produces
  the table, findings, sources and a proposed `identity-surfaces` fill from the
  pack stub.
- **Pass:**
  - [ ] every row has evidence (path or search)
  - [ ] no classification invented; any dimension offered is a draft
  - [ ] unknown owners reported as findings, not guessed
  - [ ] sources used / missing present, with a `learn` pointer for a missing tool
  - [ ] proposed fill is a diff for the operator, not a written file

## Case 3 — review an existing registry

- **Prompt:** "Is our identity surfaces list still accurate?"
- **Mode:** Critique
- **Slots:** filled; the working tree lacks `example-co/identity-config/policies/`
- **Expected behaviour:** reports `org-admin-policy` as a row with no code found,
  and any identity code found with no row.
- **Pass:**
  - [ ] stale row flagged
  - [ ] no row silently deleted

## Negative triggers

- "List our microservices" — not identity-specific; no pack skill.
- "Set up AGENTS.md for this repo" — Crew's `onboarding`.
