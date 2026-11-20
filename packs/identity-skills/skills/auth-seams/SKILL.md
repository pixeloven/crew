---
name: auth-seams
description: Use when a diff touches tokens, sessions, policy checks, identity claims, sign-in, MFA, recovery or federation flows, or trust boundaries such as webhooks and tenant filters. Classifies crossings by attacker gain, routes by the project's seams registry, seeds it.
tier: concept
requires: [plugin:crew@>=0.45.0]
expects-local: [protected-seams, identity-surfaces]
---

# Auth seams

Crew's `seam-detection` defines what a seam crossing is and how to report one;
`seam-alert-routing` defines who signs off. This skill adds the **identity
shapes** to detect. Where the project has a `protected-seams` local skill, its
entries are the record of truth — names, urgency and reviewers — and outrank
everything below; `identity-surfaces`, if present, tells you which paths are
identity code at all.

This skill never fills `protected-seams`. A project keeps one registry for every
kind of seam, with an approver behind it. With no registry, detect by the gains
below, say the registry is missing, and offer the seed entries.

## Four gains

Every auth seam protects against one thing an attacker could gain. Classify a
change by the gain it would hand over, not by the file it lives in; one change
can hand over more than one.

| Gain | The attacker… | Where it hides |
|---|---|---|
| **Impersonation** | is taken for someone or something else | token verification (audience, issuer, algorithm, key source, expiry, skew); claims accepted from a header, query or body; webhook and callback signatures; service-to-service credentials; identity linking and federation binding |
| **Bypass** | skips a step meant to stop them | sign-in, MFA, step-up, recovery, contact-address change, invite acceptance; the flow state machine; middleware order; fail-open branches around a check |
| **Escalation** | does more, or reaches further, than they may | policy checks added, removed, inlined or defaulting to allow; role, permission and scope constants; claim-to-role mapping; tenant or organisation filters; user-supplied IDs reaching privileged operations |
| **Persistence** | keeps access after it should end | session and token lifetimes, rotation, revocation on logout, password change and recovery; refresh-token reuse; cookie scope and flags; "remember me" |

Where a file lives only tells you where to look. Whether a seam is crossed
depends on what the change lets someone do: a refactor that moves a check and
keeps its behaviour is a Note; a change in what is allowed is Required.

## Method

1. **Scope the diff.** List changed files. Mark those under an
   `identity-surfaces` location or matching identity vocabulary (token, session,
   claim, policy, permission, role, scope, tenant, webhook, signature, otp, mfa,
   recovery). An unmarked file can still cross a seam; read it if it touches
   request authentication or authorization.
2. **Match the registry first.** Test each registry entry's patterns. A hit is
   reported under the entry's own name, with its urgency and reviewers.
3. **Then ask the four questions** of whatever the registry missed:
   - *Impersonation:* can something that was rejected before now be accepted as
     a user or a service?
   - *Bypass:* can a step be skipped, repeated, or reached from a new entry
     point, or does a failure now let the request through?
   - *Escalation:* can any principal do something, or touch some tenant's data,
     that it could not before?
   - *Persistence:* does any session or token live longer, survive an event it
     used to end on, or travel somewhere new?
4. **State the delta in authority.** For each crossing: who could do what before,
   who can after, and the worst outcome the new path allows.
5. **Report** in `seam-detection`'s finding format and route through
   `seam-alert-routing`. Reviewers come from the matched registry entry. For a
   crossing no entry covers, there is no default reviewer: say which gain it
   hands over and ask the operator who reviews that gain here.
6. **Propose registry entries.** For a crossing the registry did not name, draft
   an entry from [the seed file](seed-seams.md) for the operator, with urgency and
   reviewers left for them to set. Do not write it into the registry yourself.

## Diff shapes that are always Required

- an accepted audience, issuer or algorithm list widened, or signature
  verification made optional;
- a hard-coded role, group or user compare replacing a call to the policy point;
- a webhook or callback handler whose signature check is removed, skipped on
  error, or compared without constant time;
- a tenant or organisation filter dropped from a query, or taken from the request
  body instead of the authenticated principal;
- a recovery, linking or contact-change step that no longer re-authenticates;
- a fail-open branch added around a policy or token check.

## Not a crossing

- logging or metric changes that add an opaque subject or reason code (check
  `identity-ground-rules` for what may not be logged — logging a credential **is**
  a finding);
- tests that exercise a seam without changing production code;
- a dependency bump of an auth library with no config change — a Note asking for
  the changelog, not Required.

When unsure, flag. A false positive costs a short discussion.

## Onboarding: seed the registry

During Crew onboarding, or when asked, open [seed-seams.md](seed-seams.md) and
propose the entries that apply to this project for its existing `protected-seams`
registry, with each protected pattern rewritten for the code you found. Each
proposed entry is a diff the operator commits, and it needs the registry's
approver. If the project has no registry, propose creating it from Crew's
`protected-seams` stub with these entries, as one choice for the operator.

## Depth

| Mode | When | Output |
|---|---|---|
| Quick | a small diff, one gain plausible | findings list, gains checked |
| Thorough | a flow, policy or token change; or no registry | findings, authority delta per crossing, proposed registry entries |
| Critique | an existing seam review or registry | gaps, false positives, gains with no entry or no reviewer |
