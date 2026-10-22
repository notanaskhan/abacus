---
id: TASK-906
title: Staff session BFF - sign-in, callback, refresh and sign-out on auth_sessions (P-01-T09)
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-01
plan_key: P-01-T09
branch: p01-t09-staff-session
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A staff session without a second factor is refused and a reused refresh cookie revokes the session" (P-01-T09). P-01 AC 5.1.2, 5.1.4, 5.1.5 (the server half) and 2.1.6.

## Plan
- Migration `0101_auth_sessions`: three global tables (`auth_login_states`, `auth_sessions`, `auth_session_cookies`) with no app privileges, and seven SECURITY DEFINER functions granted to the app.
- `identity/staff_session.py`: the `StaffIdp` port, a generic OIDC client for the local fake, and the service: begin, complete, refresh and end.
- Routes `/v1/auth/{sign-in,callback,refresh}` under the new `PRE_SESSION` marker, and `/v1/auth/sign-out` as `OWN`.
- Registry and list edits:
  - `PUBLIC_ROUTE_EXCEPTIONS`;
  - `route_checks.MARKER_AUTH`;
  - schema_check `NON_TENANT_TABLES`, `GLOBAL_TABLES` and `DEFINER_FUNCTIONS`;
  - identity `TABLES`.
- ADR-165 and DEC-140.
- Rollback: downgrade 0101 drops the functions and tables; nothing reads them yet.

## What changed
- **Sign-in** stores the PKCE verifier and a safe return path under the SHA-256 of `state` (10 minutes, single use). `reauthenticate=true` adds `prompt=login` for step-up.
- **Callback:**
  - exchanges the code and verifies the access token with the bearer verifier;
  - refuses a token with no MFA (`mfa_required_at_sign_in`) or an unknown subject (`unknown_staff_user`), audited `auth.sign_in_refused`;
  - starts a session with the sealed refresh token;
  - sets `__Host-abacus-session`, audits `session.started` in every member firm, and lands on `/signin/callback?to=…`;
  - ends any session whose cookie is still present.
- **Refresh** needs `X-Abacus-CSRF: 1` and the app's `Origin`. It rotates the cookie and returns `{access_token, expires_in}` from the provider's refresh grant. Other outcomes:
  - a rotated-out value: 401 `session_refresh_reused`, the session ends `reuse_detected`;
  - idle or absolute expiry: 401 `session_expired`;
  - the provider refusing: the session ends `revoked`.
- **Sign-out** (`OWN`) ends only the caller's own session, tells the provider, clears the cookie and audits `session.ended`.
- **Fake sign-in server:** accepts `<origin>/v1/auth/callback`, issues refresh tokens and rotates them on the `refresh_token` grant.
- **OWN-001** no longer reads a function called after `FROM` as a table; `INTO name(` still counts.
- **Configuration:** `docs/architecture/authkit-staff-sign-in.md`.

## Decisions
- ADR-165: the three pre-session routes and the session store.
- DEC-140: 30 minutes idle and 12 hours absolute.
- The access token is the provider's, verified like any bearer token. The BFF mints nothing.
- Audit references carry integer reason codes (`staff_session.END_REASONS`, `REFUSALS`), because `Ref` holds no text.
- 401 codes are not in `error-codes.yaml`, which catalogues 409 and 422 only.

## Not done
- WorkOS adapter with provider session revoke: Q-01-T17. Plain OIDC has no revoke.
- The SPA switch to the BFF and SHL-06g: P-01-T11.
- Self-serve sign-up (SPEC-024) has no account yet, so the BFF refuses it as `unknown_staff_user`. Sign-up keeps the in-browser flow until P-01-T11 decides its path.
- An IdP-enforced MFA exemption for SSO firms: G-02.

## Progress log
- 2026-10-23: `tests/integration/test_staff_session.py` (26) passes. So do `test_oidc_server.py`, the routing and app-gate units, banned patterns, route introspection, and the schema-check definer tests.
