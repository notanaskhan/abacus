# Staff sign-in configuration (P-01-T09; ADR-141, ADR-165)

How the staff session BFF is configured, locally and on a hosted environment. Values never go in git: settings come from the environment, and hosted secrets from the vault by opaque reference.

## Settings

| Setting (env `ABACUS_…`) | Local value | Hosted value |
|---|---|---|
| `IDENTITY_ISSUER`, `IDENTITY_AUDIENCE`, `IDENTITY_JWKS` | the fake server's (`make dev` sets the JWKS; the issuer and audience are the local defaults) | the WorkOS environment's (Q-01-T17) |
| `IDENTITY_CLIENT_ID` | `abacus-web` | the WorkOS client ID |
| `IDENTITY_AUTHORIZE_URL` | `http://127.0.0.1:<9000+offset>/authorize` | the AuthKit authorize endpoint |
| `IDENTITY_EXCHANGE_URL` | `http://127.0.0.1:<9000+offset>/token` | the AuthKit token endpoint |
| `WEB_ORIGIN` | `http://localhost:<5173+offset>` | the firm app's origin, for example the staging app host |

With any of these unset, `/v1/auth/sign-in` answers 503 and nobody can sign in: since P-01-T11 the SPA has no in-browser flow of its own. `make dev` sets all of them for the fake sign-in server.

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

## When the provider is down (RB-22)

AuthKit is the only staff sign-in, so its outage is the RB-22 scenario ("Identity provider outage: break-glass admin sign-in", `docs/runbooks/README.md`; ADR-029, ADR-141). What this configuration means for it:

- **New sign-ins, step-ups and refreshes stop.** The BFF refreshes a session by exchanging its sealed refresh token at the provider's token endpoint (`identity/staff_session.py`), so a signed-in person keeps working only until their current access token expires, then lands on the sign-in error state. Fresh-MFA actions (`ConfirmItsYou`) fail at once.
- **Platform staff** sign in on the separate staff issuer, so support can still act through support sessions. Whatever break-glass path RB-22 sets for a firm's admins, it never adds a password method here (DEC-22).
- **Nothing in this file changes during an outage.** Do not repoint `IDENTITY_*` settings at another provider: a token from any other issuer is refused (ADR-165), which is the intended failure.
- After the provider recovers, run the checks above once, then record the outage in RB-22's rehearsal log.

RB-22 is Q-01's runbook (rehearse by R1); until its file is written, the index row is the reference.

## Known gaps to verify (P-01 Q2)

Each is checked on the staging WorkOS environment and, where AuthKit cannot match the handoff, recorded under Deviations in `docs/screens/SHL-06.md` (DV-7): passkeys; the DEC-35 lockout (3 failed codes → 15 minutes); the 30-day trusted device; forced re-authentication for step-up; a reliable MFA assertion for email-code users; monochrome provider buttons.
