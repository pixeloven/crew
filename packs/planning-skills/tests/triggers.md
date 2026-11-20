# Trigger cases

Each prompt is given to a session with crew and this pack installed and no other
context. **Expect** names the skill that should load, or `none of this pack`.

## Positive

| # | Prompt | Expect |
|---|---|---|
| T1 | "Support says customers keep asking to skip a week. Can you help me write this up as an idea?" | idea-shaping |
| T2 | "Which of these five items are ready for cycle planning?" | readiness-gates |
| T3 | "Group next quarter's items into themes for the roadmap review." | theme-portfolio |
| T4 | "Break this PRD into epics and stories for the team's backlog." | story-breakdown |
| T5 | "Score this PRD before I send it to review." | requirements-review |
| T6 | "Does the gift-a-box concept need security or legal involved?" | cross-functional-review |
| T7 | "Push these story drafts to our tracker." | tracker-sync |
| T8 | "Help me write a new review lens for our food-safety team." | cross-functional-review |

## Negative

| # | Prompt | Expect | Why |
|---|---|---|---|
| N1 | "Plan the refactor of module X." | none of this pack (crew `plan-generation`) | agent work plan, not a product backlog |
| N2 | "Break this migration into phases and delegate them to agents." | none of this pack | agent orchestration |
| N3 | "Write the acceptance tests for the checkout service." | none of this pack | code testing, not product acceptance criteria |
| N4 | "Review this pull request for security issues." | none of this pack (crew review) | code review, not a concept-stage lens |
| N5 | "Create a ticket for this bug." | none of this pack's core skills; tracker-sync only if the operator confirms it is a planning draft | tracker writes are never taken by a core skill |
| N6 | "Update the status field on these issues." | none of this pack's core skills | tracker admin |
| N7 | "Write an ADR for moving to the new queue." | none of this pack | ADRs stay in crew |
| N8 | "Explain what a product roadmap is for." | none of this pack | explanation, not a planning artifact |

## Pass checklist

- [ ] Every positive prompt loads its expected skill and no other skill from this pack.
- [ ] N1–N4 and N7–N8 load no skill from this pack.
- [ ] N5–N6 load no core skill; no tracker write happens without confirmation.
