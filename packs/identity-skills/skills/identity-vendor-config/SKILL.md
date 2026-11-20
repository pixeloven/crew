---
name: identity-vendor-config
description: Use when reviewing a change to identity-vendor configuration held as code (identity provider, customer identity platform, policy engine), or checking live vendor state against it. A per-object ledger of writers, live, code and pending state; next steps follow from what either side winning costs.
tier: concept
requires: [plugin:crew@>=0.45.0]
expects-local: [identity-surfaces, protected-seams, agent-runtime]
---

# Identity vendor config

A vendor configuration object — a flow, a policy, a session setting, an allow
list — rarely has a single author. The repository writes it on apply; people
write it in the admin console; the vendor writes it through defaults and
migrations; another pipeline may write it too. This skill keeps one **ledger**
with a row per object, and answers both kinds of question from it: *is this
change safe to ship?* and *does what the vendor runs match what we think it
runs?*

Vendors are named by role — identity provider, customer identity platform,
policy engine, risk service — never assumed. Where the project has an
`identity-surfaces` local skill, its vendor rows say which config is held as
code and where; its `protected-seams` registry says which config paths need
sign-off. With both empty, find config directories by their shape (flow, policy,
role, connection, application definitions) and propose the rows.

A vendor export can carry credentials and user data alongside configuration.
Work from object names and settings; leave secrets, keys and user records out of
every cell, query and appendix (`identity-ground-rules`).

## The ledger

| Column | Holds |
|---|---|
| **Object** | one configuration object, and every application or population that uses it |
| **Writers** | every way it can change, and where: repository apply, console, vendor defaults or migration, another pipeline |
| **Live** | what the vendor is running now, or *unknown* |
| **Code** | what the repository currently says |
| **Pending** | what the change under review would make it (blank for a sweep) |
| **If code wins** | the effect of making live match the repository (or the pending version, for a change) |
| **If live wins** | the effect of making the repository match live |
| **Next step** | what happens to this row, who does it — derived from the two cells before it |

Fill the state cells with behaviour: what a person reaching the object is asked
for and where they end up, not the text of a file. When two exports describe the
same behaviour, the row has no difference.

## Filling the cost cells

The two *If … wins* cells are where the review happens. Each one says, in a
sentence or two:

- **who it reaches** — which applications and populations, and whether all at
  once or gradually;
- **what it changes for them** — access gained or lost, a step that strands
  people (a lockout, a loop, a step nobody can complete);
- **what it opens** — a step removed or made optional, a longer lifetime, a
  wider redirect or origin list, a default role, a new trusted identity source;
- **what outlasts it** — enrolments, linked accounts, tokens and sessions
  created while it held, which stay even if the other side wins later. Say
  plainly when there is no way back.

Route every opening through `auth-seams`, under the gain it hands an attacker
and the registry entry it matches.

## Deriving the next step

There is no fixed list of steps. Read each row's two cost cells and apply one
rule: **the side whose outcome is both safe and intended wins.**

- Code wins → the step is an apply, once the live cell is known.
- Live wins → the step is a pull request that brings the repository up to live,
  so the next apply does not undo it.
- **Neither is known to be both → the row blocks.** Its step names what is
  missing — the live value, the intent behind a value, a reviewer for an opening
  — and who can supply it.

*Intended* needs evidence: a pull request, a ticket, the object's owner saying
so. A value only live has is someone's decision until shown otherwise; an apply
over it reverses that decision silently, so until its intent is known the row
blocks. An unknown live cell blocks any apply on its row. An object the
repository deliberately leaves to the console is fine when the repository says
so; when it does not, the step is to write that down.

A change is clear to ship only when every row it touches has a winner; one
blocking row holds it. Name people by role or opaque ID in any cell.

## Building it

- **Choose the rows.** For a change: every object the diff touches, plus every
  object that shares one of them — a flow or policy used by several applications
  changes all of them at once. For a sweep: every object the repository manages,
  plus anything the vendor shows that the repository does not.
- **Name the writers.** A writer nobody expected is itself a finding.
- **Get live state read-only**, through whatever the capability map offers: the
  vendor's admin API, the config tool's plan or diff command, an export. With
  nothing, hand the operator the command and fill the column from what they
  paste.

## Output

```markdown
## Vendor config ledger — <PR #N | sweep> — <vendor role> (<date>)

**Outcome:** <clear to ship | held by N blocking rows | N rows need a step>

| Object | Writers | Live | Code | Pending | If code wins | If live wins | Next step |
|---|---|---|---|---|---|---|---|

### Openings raised through auth-seams
- <object>: <gain> — <registry entry, or reviewer asked for>

### Sources
- used: <repository commit, capability or command>
- missing: <what would have filled the live column — see `learn`>

### Appendix: commands and queries
<every command run or handed over>
```

## Depth

| Mode | When | Output |
|---|---|---|
| Quick | a small config PR | ledger rows for the touched objects, outcome |
| Thorough | a flow or policy change, a shared object, or a first sweep | full ledger including sharing objects, openings, what outlasts each side |
| Critique | an existing review or comparison | missing rows, unexpected writers, live columns never filled, steps not derived from the cost cells |

## Not this skill

Application code that calls a vendor SDK is `auth-seams` territory. A vendor
outage write-up uses Crew's `incident-runbook-template`.
