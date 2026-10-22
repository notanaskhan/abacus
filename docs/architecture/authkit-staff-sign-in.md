# Staff sign-in configuration (P-01-T09; ADR-141, ADR-165)

How the staff session BFF is configured, locally and on a hosted environment. Values never go in git: settings come from the environment, and hosted secrets from the vault by opaque reference.

## Settings

| Setting (env `ABACUS_…`) | Local value | Hosted value |
|---|---|---|
| `IDENTITY_ISSUER`, `IDENTITY_AUDIENCE`, `IDENTITY_JWKS` | the fake server's (`make dev` sets them) | the WorkOS environment's (Q-01-T17) |
| `IDENTITY_CLIENT_ID` | `abacus-web` | the WorkOS client ID |
| `IDENTITY_AUTHORIZE_URL` | `http://127.0.0.1:<9000+offset>/authorize` | the AuthKit authorize endpoint |
| `IDENTITY_TOKEN_URL` | `http://127.0.0.1:<9000+offset>/token` | the AuthKit token endpoint |
| `WEB_ORIGIN` | `http://localhost:<5173+offset>` | the firm app's origin, for example the staging app host |

With any of these unset, `/v1/auth/sign-in` answers 503 and the old in-browser PKCE flow keeps working until P-01-T11 switches the SPA.

## The provider side (AuthKit)

1. Redirect URI: `<WEB_ORIGIN>/v1/auth/callback`. That is the only one; the SPA's `/signin/callback` is where the BFF sends the browser afterwards, not a provider redirect.
2. Methods: Microsoft, Google and email code. No password method (DEC-22).
3. MFA: required for every non-SSO user (TOTP). The BFF also refuses any token without `amr: ["mfa", …]`, whatever AuthKit is set to (ADR-165).
4. Refresh tokens: on. The BFF keeps them sealed with the platform key; the browser never sees them.
5. Lockout: the DEC-35 values wherever AuthKit lets them be set.

## Checks after a change

- `GET /v1/auth/sign-in` redirects to the authorize endpoint with `code_challenge_method=S256`.
- A sign-in without a second factor lands on `/signin/callback?error=mfa_required_at_sign_in`.
- The `Set-Cookie` header names `__Host-abacus-session` with `HttpOnly; Secure; SameSite=strict; Path=/` and no `Domain`.
- Refreshing the same cookie twice gives 401 `session_refresh_reused` and ends the session.
