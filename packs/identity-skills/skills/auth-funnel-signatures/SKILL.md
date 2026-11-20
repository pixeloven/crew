---
name: auth-funnel-signatures
description: Use when interpreting auth or MFA funnel telemetry, building a funnel baseline, or judging whether a spike is an attack, a deploy or noise. Derives baselines and anomaly signatures from whatever events exist, grades signal reliability and rules out confounders first.
tier: concept
requires: [plugin:crew@>=0.45.0]
expects-local: [identity-event-schema, agent-runtime]
---

# Auth funnel signatures

The shared method behind `account-investigation` and `risk-signal-trends`: turn
whatever auth events an organisation emits into a baseline, describe departures
from it as signatures, and refuse to attribute one before the confounders are
ruled out. It assumes no event names and no store. Where the project has an
`identity-event-schema` local skill, its catalogue, reliability table and change
log pointer come first; with it empty, this skill discovers them and proposes
the fill.

PII and indicator rules: `identity-ground-rules`. Signatures are **patterns** —
ratios, shapes, timings — never the values of the traffic that produced them.

## 1. Find the funnel

1. Read the capability map in the project's `agent-runtime` fill. Note which of
   these exist: a warehouse (`mcp:warehouse`), product analytics
   (`mcp:analytics`), logs (`mcp:logs`), a vendor admin or audit API, or nothing.
2. Discover the auth events: list tables, event names or log fields matching
   sign-in, challenge, OTP, MFA, verify, session, token, recovery. With no
   capability, ask the operator for the event list or hand them a discovery
   query for their store.
3. Order the events into a funnel: **start → identifier → challenge issued →
   challenge passed → session established**, plus side branches for recovery,
   enrolment and failure. Real flows differ; keep the steps you can evidence.
4. Propose the event catalogue rows for `identity-event-schema`, and the shapes
   from §4 the events can evidence, as candidate signal families.

## 2. Grade the signals

Before a finding leans on a signal, establish whether the signal deserves it.
Measure, do not take the documentation's word:

- **Coverage** — the share of the events it should describe where it is actually
  present, overall and per structural segment. Missing is **unknown**, never
  `false`, and coverage that differs by segment biases every comparison.
- **Spread** — whether it varies. A signal that takes one value for nearly all
  traffic cannot separate anything.
- **Latency** — how long after the event it lands in the store. A signal that
  arrives after the window closes cannot inform that window.
- **Blind spots** — where it is wrong by construction: what it needs that some
  traffic lacks (history, a client version, a platform), and when it was last
  changed upstream.
- **Validation** — whether it agrees with ground truth: cases already confirmed
  or ruled out, a population known to be clean, or a second independent signal.
  Unvalidated is a finding in itself.

From these, grade its **use**: **rely** (validated, covered where it is used),
**corroborate** (informative but partial, slow or unvalidated — never the only
evidence), or **cite only** (missing, flat or contradicted). Record the date you
measured; a grade past the reliability table's review interval is **stale** and
is re-measured before anything leans on it.

Every finding names each signal it uses with its grade.

## 3. Build the baseline

- **Normalise to the start of the funnel**: divide each step by the number of
  sessions that entered the funnel in the window, so traffic volume does not
  masquerade as behaviour.
- **Pick a comparison window** of the same length and weekday mix: the prior
  period, or the same period a cycle earlier.
- **Segment only by structure** the schema provides: platform, flow, client
  version, new versus returning account. A segment defined by an indicator value
  is supplied by the operator, used only in the live query, and written as a
  placeholder everywhere else.
- Record each step's rate and its normal variation (several prior windows, not
  one).

## 4. Describe the signature

A departure is a **signature** when it is outside normal variation and has a
shape. Common shapes, described without values:

| Shape | What it looks like |
|---|---|
| Challenge flood | challenge issued rises while challenge passed stays flat |
| Credential testing | identifier and failure steps rise; success rate per attempt falls |
| Recovery pressure | recovery starts rise relative to sign-in starts |
| Abandoned challenge | many challenges issued per session with no pass and no retry delay |
| Step skip | session established without the step before it appearing |
| Uniform timing | inter-step times far narrower than the baseline spread |

## 5. Rule out confounders — before attribution

1. **Is the shift shared?** Hold the segment against a comparison population
   (`risk-signal-trends` describes choosing one). If that population departs
   from its own normal range in step with the segment, call it a **shared
   shift** — something common to all traffic changed — and stop attributing.
2. **Overlay the change log.** Use the change/experiment-log pointer in
   `identity-event-schema`. A deploy, flag flip or experiment touching the flow in
   the window is the first explanation to test.
3. **Check instrumentation.** A new event, a renamed field, a sampling change or a
   pipeline delay produces signatures too.
4. **Check the calendar**: a product launch, a marketing send, a holiday.

Only a departure that survives all four is reported as **likely abuse**, with a
confidence. Otherwise it is reported as what it most likely is.

## Output

Findings in Markdown: the funnel used, the baseline window, each signature with
the signals behind it and their grades, the confounders checked and their result,
and a confidence. Then **Sources** (used / missing) and an **Appendix: queries** —
every query run or handed over, with placeholders for any operator-supplied
predicate. When a finding is later confirmed or ruled out, record the outcome
against the signals used, so their grades can be revisited.

## Depth

| Mode | When | Output |
|---|---|---|
| Quick | a single "is this spike real?" | one comparison, confounder checks 1–2, verdict |
| Thorough | a new baseline or an empty event-schema slot | funnel, reliability grades, baseline, proposed slot fill |
| Critique | an existing dashboard, alert or report | unreliable signals, missing confounder checks, unnormalised rates |
