# Negative triggers

Near-miss prompts. For each, the listed pack skill must **not** load, and the
expected skill (or none) should. Overlap with Crew is the main risk: a generic
task must reach Crew's skill, not an identity one.

| Prompt | Must not load | Should load |
|---|---|---|
| "Review this PR" (a styling-only diff) | `auth-seams` | Crew `pr-review-checklist` |
| "Scan this Kubernetes diff for protected changes" | `auth-seams` | Crew `seam-detection` |
| "Who should sign off on this seam crossing?" | `auth-seams` | Crew `seam-alert-routing` |
| "Write the incident report for last night's outage" | `account-investigation` | Crew `incident-runbook-template` |
| "Learn how our warehouse CLI works" | `auth-funnel-signatures` | Crew `learn` |
| "Explain OAuth to a new hire" | any pack skill | none |
| "Our checkout conversion fell 5%" | `auth-funnel-signatures`, `risk-signal-trends` | none |
| "Map our microservices" | `identity-surface-map` | none |
| "Lock this user's account now" | `account-investigation` acting | the agent declines to act; may offer to investigate |
| "Install the identity vendor's Terraform provider" | `identity-vendor-config` | none |
| "Set up this repo for Crew" | `identity-surface-map` | Crew `onboarding` |

**Pass:** for each row, the transcript shows the expected skill (or none)
loaded, and no listed pack skill loaded.
