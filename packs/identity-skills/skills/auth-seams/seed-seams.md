# Auth seam seed entries

Starter entries for a project's **existing** `protected-seams` registry (Crew's
stub at `templates/local-skills/protected-seams.md`), one per gain an attacker
could take, written in that stub's terms: the **protected pattern** to scan a
diff for, the **risk** if it changes silently, and the **response**. Copy the
ones that apply, split an entry where the project's code splits naturally (a
separate entry for webhook verification, say), rewrite each pattern for the
project's real paths and libraries, and commit them through the registry's
approval rule. These are shapes, not facts: nothing here names a vendor, path or
team.

The **response** — urgency and who signs off — is deliberately left blank. That
is the project's call, recorded once in its registry; this pack does not make it.

No entry may hold a secret, a personal identifier, or an attack indicator.

---

## Impersonation

- **Protected pattern:** calls that verify tokens, and the options passed to
  them; accepted audience, issuer and algorithm lists; where keys or key sets
  come from; expiry, not-before and clock-skew settings; code that mints tokens;
  claims read from request headers, query strings or bodies; signature checks on
  inbound webhooks and callbacks; service-to-service credentials and their
  scopes; identity linking and federated-login binding.
- **Risk:** each service that believes an identity inherits whatever this code
  accepts. Widen an audience, make a signature optional, or read a claim from
  the client, and a caller passes as someone it is not.
- **Response:** `<urgency and reviewers — set by the project>`

## Bypass

- **Protected pattern:** sign-in, MFA enrolment and challenge, step-up, account
  recovery, contact-address change, invitation acceptance; the state machine or
  flow configuration that sequences them; the order of middleware or filters;
  `catch`, timeout and default branches wrapped around a check.
- **Risk:** a step that can be skipped, re-entered or fails open lets through
  exactly the person it exists to stop. Recovery and contact change go around
  sign-in on purpose, so they earn the same scrutiny.
- **Response:** `<urgency and reviewers — set by the project>`

## Escalation

- **Protected pattern:** calls to the policy evaluation point or shared
  authorization helper; role, permission and scope constants; mapping from
  claims to roles or tenants; tenant or organisation filters on queries;
  identifiers from the request that reach privileged operations.
- **Risk:** a check that is moved, inlined, defaulted to allow, or told its
  tenant by the request changes who may do what — and often no test notices.
- **Response:** `<urgency and reviewers — set by the project>`

## Persistence

- **Protected pattern:** session creation and rotation; idle and absolute
  timeouts; token lifetimes; revocation on logout, password change and recovery;
  handling of refresh-token reuse; cookie `Secure`, `HttpOnly`, `SameSite` and
  domain attributes.
- **Risk:** a session that lasts longer, reaches wider, or survives an event
  that should end it keeps a stolen credential useful for longer.
- **Response:** `<urgency and reviewers — set by the project>`
