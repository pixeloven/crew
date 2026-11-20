# Tests

These are scenario cases, run by hand or by an agent harness: give the agent the
trigger prompt with the named fixture and slot state, then grade the output against
the pass checklist. There is no executable runner — the skills are instructions, so
the unit under test is an agent's behaviour, not code.

| Path | Holds |
|---|---|
| [`scenarios/`](scenarios/) | one file per skill: trigger, fixture, slot state, mode, expected behaviour, pass checklist |
| [`triggers.md`](triggers.md) | positive and negative trigger prompts across the pack, including prompts no skill may take |
| [`fixtures/`](fixtures/) | sample inputs, and filled slots for the fictional Example Co |

## Slot states

Every skill has at least two runs:

- **Filled** — copy `fixtures/example-co/<slot>.md` into the test project's overlay
  as `.agents/skills/example-co-<slot>/SKILL.md` (symlinked into `.claude/skills/`
  on Claude Code).
- **Empty** — no fill for any of this pack's slots. The skill must still produce a
  useful result on its generic defaults, say that it used them, and propose slot
  content rather than assume it.

## Grading

A case passes when every checklist item holds. Record runs as
`<date> <harness> <case id> pass|fail <note>`; a failure names the checklist item.
Re-run the trigger cases whenever a description changes.

## Checks common to every case

- The output opens with crew's reporting-contract opening line (what needs the operator's call).
- No tracker, document or message is written without the operator seeing every field first.
- Nothing names a real organisation, product or person beyond what the fixture supplies.
