---
name: activation-contracts
description: How an agent role gets woken — the trigger interface (event → dispatch → output), which roles are dispatched interactively versus triggered autonomously, and reference wiring for issue events and scheduled sweeps. Load when a role should run without someone asking it to, when wiring CI or a scheduler to an agent, or when deciding whether work belongs to a cheap triggered role instead of the session you are in.
tier: concept
requires: [external:github]
---

Roles describe autonomy readily — "runs on a schedule", "fires on alerts", "routes incoming work" — and then wait to be asked, because nothing wires the event to the dispatch. A role with no trigger is a role that only runs when a human remembers it exists, which in practice means the expensive session absorbs its work.

This skill is the contract that makes a trigger portable, and reference wiring for the two shapes that cover most cases.

## Two activation models

Every role is one or the other. Say which in your routing table, because they need different things from you.

| Model | Woken by | Needs | Typical roles |
|---|---|---|---|
| **Interactive dispatch** | the agent you're talking to | nothing — the routing table is enough | planning, implementation, review |
| **Autonomous trigger** | an event or a schedule, with no human in the loop | infrastructure you deploy | intake, diagnosis, curation, drafting |

A routing table that lists both without distinguishing them implies every role is one dispatch away. Four of them aren't, and that gap is why they stay dormant.

## The trigger interface

Any activation — a CI workflow, a cron schedule, a webhook — supplies the same four things. Keep them separable so the wiring can change without touching the role.

1. **Event** — what happened, with enough payload to act on (issue number, alert name, run id). Normalise it: the role shouldn't parse three different shapes for "something needs triage".
2. **Dispatch** — invoke the role with a packet meeting the contract in `orchestration-patterns`. A triggered worker starts cold *and* has no human to ask, so under-specifying here fails silently rather than loudly.
3. **Output location** — where the result lands: an issue comment, a label, a review note, a file. Decide before wiring. A triggered role whose output goes nowhere observable is indistinguishable from one that never ran.
4. **Failure signal** — what happens when the run fails. Silence is the default and the wrong one; a trigger that fails quietly is worse than no trigger, because it looks like nothing needed doing.

Set a **budget** on every trigger — turn or token caps where the harness offers them. Triggered work has no human watching cost accumulate.

## Choosing what to trigger

Trigger a role when its work is **recurring, bounded, and cheap to be wrong about**. Intake classification, health sweeps, and lint triage all qualify: they run often, each run is small, and a mistake costs a comment rather than a commit.

Don't trigger work that needs judgment about scope, touches protected seams, or writes to anything durable without review. Those want a human deciding to start them.

**The economics matter more than they look.** The triggered roles are usually the cheap ones. Left untriggered, their work doesn't vanish — it gets absorbed into whichever expensive session notices, at a much higher cost per unit. That's the argument for wiring them, and it's also why *not* delegating to them mid-session is a real cost rather than a stylistic preference.

## Reference wiring

Two templates, both starting points rather than drop-ins:

- **`templates/activation/github-action-intake.yml`** — issue and PR events → classify, label, route. The most common first trigger, and the cheapest to prove out.
- **`templates/activation/scheduled-sweep.yaml`** — a Kubernetes CronJob for periodic diagnosis or curation. Adapt the schedule and the runner image; the shape is what matters.

Both write results where a human will see them, and both fail loudly.

## Prerequisites that fail silently

Wire these before wiring the trigger, or the first run will look like a no-op:

- **Labels must exist.** A classifier applying `domain:*` labels to a repo without them silently applies nothing. Create the taxonomy first.
- **The runner needs credentials scoped to its job** — read the event, write the output, nothing more. A triggered role is unattended; least privilege is the whole safety margin.
- **Deduplicate.** A schedule that files an issue each run produces a queue of duplicates within a week. Check for an open one first.
- **Verify by observing, not by config.** After wiring, trigger it once for real and confirm the output landed. The `doctor` skill's shadowing check exists because config that looks right and does nothing is the recurring failure here.
