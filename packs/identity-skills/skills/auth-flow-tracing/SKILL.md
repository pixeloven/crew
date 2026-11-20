---
name: auth-flow-tracing
description: Use when a sign-in, token, session or identity flow spans more than one service or a vendor and you must explain what happens to the request end to end, or why it fails in between. Follows the identity backwards from where it is used to where it was proven, step by step.
tier: concept
requires: [plugin:crew@>=0.45.0]
expects-local: [identity-surfaces, protected-seams]
---

# Auth flow tracing

A request carries an identity: *this user, in this tenant, at this assurance
level, for this audience*. On the way to the code that acts on it, that identity
changes form many times — a password becomes a session, a session becomes a
token, a token becomes a header or a service credential — and every change of
form is a place where it can be lost, distorted or forged. This skill follows
that one identity and writes down each change of form.

Where the project has an `identity-surfaces` local skill, use it to name places
and owners; where it has a `protected-seams` registry, mark the steps it names.
Neither is required: with both empty, the trace finds its steps in code and
config and reports which ones it could not confirm.

## Method

### Pin down what must arrive

Write one sentence: which facts about the caller the **decision point** needs,
and where that decision point is — the handler, policy check or vendor rule that
finally acts on the identity. *"The refund handler needs the member's account
ID and tenant, with step-up done in the last ten minutes."* One identity, one
decision point, per trace.

### Walk backwards to where it was proven

Start at the decision point and repeatedly ask *where did this come from?* Each
answer is a step. Keep going until you reach the **origin**, the place where the
user or service actually proved who it is: a credential check, a vendor
assertion, a signed service credential. Read code and config for each answer —
middleware, gateway rules, handlers, outbound calls, vendor redirects and
callbacks. For each step, record:

- **arrives as** — the form it takes on the way in: cookie, bearer token, signed
  assertion, header, service credential, and the claims it carries, by name;
- **proven by** — what this step checks to believe it, or *nothing*;
- **vouched for by** — who issued or signed what it believes;
- **leaves as** — the form handed to the next step toward the decision point;
- **lost or added** — claims dropped, renamed, widened or given a new meaning;
  an assurance fact (MFA done, step-up time) that does not survive.

Walking backwards keeps the trace on what the decision depends on. Branches that
never feed it can be named and left out.

### Find the weak links

A step is a **weak link** when it accepts what arrives without proof — a header
or claim set upstream and never verified here — or when the identity leaves
meaning less, or more, than it arrived meaning. Each weak link is reported even
if nothing is broken today: it is an impersonation path waiting for a caller.
Label every step with the `auth-seams` gain it guards and any registry entry it
matches.

### For a failure: bracket the break

Mark the latest step where the identity is still what the decision point needs
(**last intact**) and the earliest where it is not (**first wrong**). The break
lies between them; narrow the gap until they are adjacent. Typical breaks: a
claim not carried, an audience that does not match, clock skew, a cookie not
sent across a domain, a redirect outside an allow list. Prefer evidence — a log
line, a config value, a test — over inference, and label which is which.

### Confirm with runtime evidence

If the capability map offers logs or traces (`mcp:logs`, an APM tool), confirm
the order of steps and the break with aggregate, opaque-ID evidence. Without one,
hand the operator the exact search to run and read back what they paste. Never
paste a token or cookie into the trace; refer to it by kind (see
`identity-ground-rules`).

## Output

```markdown
## Identity journey — <what must arrive> at <decision point>

Origin: <where the identity is proven>
Covers / leaves out: <branches included and excluded>

### Chain of custody (decision point first)
| Step | Where | Owner | Arrives as | Proven by | Vouched for by | Leaves as | Lost or added | Seam |
|---|---|---|---|---|---|---|---|---|

### Weak links
- step N: <what is accepted unproven, or how meaning shifts> — <fact / inference, source>

### Break (failures only)
Last intact: step N. First wrong: step M. Cause: <...> — <fact / inference, source>

### Claim meanings
- <claim or header>: set at step N, read at steps M..K, means <...>

### Sources
- used: <repos, configs, logs, traces>
- missing: <steps not confirmed, and what would reach them>

### Follow-ups
- <fix, test to add, owner to involve, seam entry to propose>
```

The chain is a durable artifact: opaque IDs and logical names only.

## Depth

| Mode | When | Output |
|---|---|---|
| Quick | a "what vouches for what" answer | chain with arrives-as / leaves-as, unconfirmed steps flagged |
| Thorough | a failure, a design change, or a security review | full chain, weak links, break bracket, claim meanings, follow-ups |
| Critique | an existing trace or design doc | steps missing, trust never proven, claim meanings out of date |

## Pitfalls

- A diagram is a claim about the flow; code and config are the evidence.
- The vendor is not a black box to step over: its callback, claim mapping and
  session cookie are steps in the chain like any other.
- A check done upstream is not a check here. Record *proven by: nothing* when
  that is the truth.
- Two identities in one trace. Split them, and link the traces.

## Composes with

`identity-surface-map` for unknown places and owners; `auth-seams` for
classifying each step; `identity-vendor-config` when the break is in vendor
configuration; Crew's `incident-runbook-template` when the trace becomes an
incident report.
