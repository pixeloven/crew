# Example Co — identity surfaces (fixture fill)

## Dimensions

| Dimension | Values | What each value means |
|---|---|---|
| data held | `secrets`, `claims-only` | `secrets`: the surface stores or mints credentials, keys or tokens. `claims-only`: it only reads identity claims already validated elsewhere. |

## Surfaces

| Surface | Location | Kind | Ships changes | Touches identity by | Owner | Path ownership | Data held |
|---|---|---|---|---|---|---|---|
| `auth-api` | `example-co/auth-api` | code | identity team | issues sessions, validates tokens | identity team | `CODEOWNERS: /` | secrets |
| `token-issuer` | `example-co/auth-api/issuer/` | code | identity team | issues tokens | identity team | `CODEOWNERS: /issuer/` | secrets |
| `checkout-auth-middleware` | `example-co/checkout/src/middleware/auth.ts` | code | payments team | validates tokens through the shared auth library | payments team | `CODEOWNERS: /src/middleware/` | claims-only |
| `org-admin-policy` | `example-co/identity-config/policies/` | vendor tenant (as code: yes) | identity team | evaluates policy | identity team | `CODEOWNERS: /policies/` | secrets |
| `hosted-login-flows` | `example-co/identity-config/flows/` | vendor tenant (as code: yes) | identity team | hands users to vendor-hosted sign-in | identity team | `CODEOWNERS: /flows/` | secrets |

## Vendors

- identity provider — hosts `hosted-login-flows`; config held as code in
  `example-co/identity-config`; no admin capability in the capability map.
- policy engine — evaluates `org-admin-policy`; config held as code.
