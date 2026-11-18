---
id: TASK-8548
title: "G-04-T14: the console's staff sign-in BFF on the staff issuer (red)"
spec: SPEC-680
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: g04-t14-console-staff-bff
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-18
updated: 2026-11-18
plan_key: G-04-T14
---

## Objective
DEC-5528's follow-up: Accrued platform staff sign in to the console through a BFF on the staff
issuer, shaped like the firm's (ADR-141, ADR-165): authorization code with PKCE on the server, an
opaque `__Host-` cookie stored only as a SHA-256, rotated on every refresh (reuse ends the whole
session), staff MFA required at sign-in and on every refresh, 30 minutes idle and 12 hours in all
(DEC-140). The page keeps only a memory access token; the CSP's `connect-src 'self'` holds.

## Plan (red)
1. **Migration 0969** (`0969_platform_staff_sessions.py`, revises 0968; first 0955 on 0954): two global tables with no
   app privileges, `platform_staff_sessions` (issuer, subject, sealed provider refresh token,
   mfa_at, idle and absolute expiries, end reason) and `platform_staff_session_cookies` (every
   issued value as a SHA-256, retired on rotation). SECURITY DEFINER functions, search_path
   pinned, EXECUTE to `abacus_app` only: `platform_staff_session_start`, `…_rotate` (`ok`,
   `unknown`, `ended`, `reused`, `idle`, `absolute`), `…_set_refresh`, `…_revoke`, `…_end`. The
   sign-in state reuses `auth_state_put` / `auth_state_take` (0101). Reversible.
2. **Registries:** schema_check's global-table lists and `DEFINER_FUNCTIONS`; identity's
   `TABLES`; config `platform_staff_client_id`, `platform_staff_authorize_url`,
   `platform_staff_token_url`, `console_origin` (internal; no secret value anywhere).
3. **`identity/platform_staff_session.py`** (PROTECTED): begin, complete (the exchanged token is
   verified by the *staff* verifier; refused without MFA or without a platform role), refresh
   (rotate, provider refresh, re-verify the same subject with MFA, else revoke), end. Reuses the
   firm BFF's `OidcStaffIdp`, `ProviderTokens` and `safe_return_to`. Audit: `session.started` /
   `session.ended` / `auth.sign_in_refused` on the platform trail, identifiers only.
4. **Routes** `/v1/platform/auth/{sign-in,callback,refresh,sign-out}` under `PRE_SESSION`
   (sign-out under `STAFF`), added to `PRE_SESSION_PATHS`; the cookie `__Host-abacus-console`,
   `Secure; HttpOnly; SameSite=Strict; Path=/`; refresh needs `X-Abacus-CSRF: 1` and the console's
   own Origin; every answer `Cache-Control: no-store`.
5. **Console:** `console/auth.ts` (memory token, single-flight refresh, top-level sign-in
   navigation) and `StaffAuth` asks it whether a session exists; generated client attaches the
   bearer for `/v1/platform/*`.
6. **Tests (end pass):** unit for the module with a fake IdP and verifier (start, rotation, reuse,
   idle, MFA refused, no role refused, safe return path, CSRF and Origin on refresh); the
   migration up-down-up and schema_check; web tests for the console auth client.
7. **Rollback:** drop the routes (unmatched paths 404); 0969 downgrades cleanly; the console is
   the sign-in gate again.

## Progress log
- `2026-11-18` — Plan written before building (red). Gates, tests and a security review at the
  end pass.
- `2026-11-18` — Built: 0955 (two global tables, five definers), `platform_staff_session.py`, `console_auth_routes.py`, PRE_SESSION paths, config fields, schema_check and identity registries; console `auth.ts`, StaffAuth refusal, ConsoleShell callback and signed-in frame. `tests/integration/test_g04t14_console_bff.py` (8) green on the first run; `console/auth.test.ts` (3); schema_check clean; the production console build's dist check clean. Not done: a real staff IdP (staging), the console host and WAF allowlist, PLT-01's live hosts behind the session, the security review (end pass).
- `2026-11-18` — Security review (inline, ADR-078 red): cookie (`__Host-`, Secure, HttpOnly, SameSite=Strict, SHA-256 only, rotated, reuse ends the session), CSRF and exact-Origin on refresh and sign-out, safe return path, MFA and a console role at sign-in and on every refresh with the same issuer and subject, definers with pinned search_path and EXECUTE to `abacus_app` only. Two low findings fixed: (1) every refresh moved the idle clock — now only a refresh marked `X-Abacus-Activity: user` (the shell's page-load refresh) does, as the firm BFF (0220, DEC-535); (2) the sign-out audit derived the staff id from the configured issuer — now from the session row's. Generated security suite regenerated for the four routes.
- `2026-11-18` — End pass after S50 merged (main d394ba3c1): main merged in, client and security suite regenerated, migration renumbered 0955 → 0969 on 0968 (S50's 0960–0966, then its schema fix 0968, #2331). The four paths added to ROUTE-001's exception list (route introspection had flagged them). Green: BFF integration (8), S49 migrations incl. a 0969 down-up and no-app-privilege test, route introspection, identity unit, contracts, web tsc and vitest, check-fast. schema_check's 12 problems are main's (S50 tables), not this branch's.
