# Example Co — protected seams registry (fixture fill)

## Seams

### Payment token scope

- **Pattern:** `scope` lists in `checkout/src/middleware/auth.ts`.
- **Risk:** a widened scope lets any member token authorise refunds.
- **Response:** flag, Required.

## Registry ownership

Approver: the identity on-call lead. New entries by PR with that approval.
