# Scenarios: tracker-sync

## TS-1 Dry run, filled slot, tracker connected

- **Prompt:** "Push these slices to the tracker." + SB-2 output
- **Slots:** [Example Co tracker-fields](../fixtures/example-co/tracker-fields.md); tracker connected
- **Mode:** Quick (first sync)
- **Pass checklist**
  - [ ] Lists every item: create vs update, every field and value, every link.
  - [ ] Maps `size` to project field `Size`, `parent` to a sub-issue relation.
  - [ ] Writes nothing; waits for confirmation.

## TS-2 Write and re-run

- **Prompt:** "Go ahead." (continuing TS-1), then the same push again.
- **Mode:** Thorough
- **Pass checklist**
  - [ ] Parents created before children.
  - [ ] `tracker-key:` filled in each draft after the write.
  - [ ] Second run updates the same items; nothing duplicated.
  - [ ] Assignees and `Priority` never written (write policy).

## TS-3 Unresolved field

- **Prompt:** "Push this story." + a story with `stage: Validate` (not an allowed value)
- **Slots:** Example Co tracker-fields
- **Pass checklist**
  - [ ] Stops for `stage`; does not guess a mapping.
  - [ ] Offers to leave the field out or fill the slot, naming crew `learn`.

## TS-4 Empty slot, no tracker connection

- **Prompt:** "Get these stories into our tracker."
- **Slots:** empty; no tracker capability
- **Pass checklist**
  - [ ] Does not fail: writes an import file with the pack's own field names as columns, or paste-ready text.
  - [ ] Tells the operator to map columns in the tracker's import screen.
  - [ ] Asks for the resulting keys to fill `tracker-key:` lines.
  - [ ] Suggests crew `learn` to draft `tracker-fields` once a tracker is connected.

## TS-5 Empty slot, tracker connected

- **Prompt:** "Push these stories."
- **Slots:** empty; tracker connected
- **Pass checklist**
  - [ ] Refuses a direct write (no identifiers); offers the import-file path and crew `learn`.

## TS-6 Pull

- **Prompt:** "Pull the open Pitches into drafts so we can score them."
- **Slots:** Example Co tracker-fields
- **Pass checklist**
  - [ ] One draft per item with header filled by the reverse map; unmapped fields listed separately.
  - [ ] Tracker unchanged.

## TS-N Negative triggers

| Prompt | Must not happen |
|---|---|
| "Score these ideas." | tracker-sync loads or any tracker write |
| "Create a bug ticket for this crash." | tracker-sync writes without the operator confirming it is a planning draft |
