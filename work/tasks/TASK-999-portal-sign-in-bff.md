---
id: TASK-999
title: Portal sign-in BFF core — migration 0116, start/verify/resend/refresh/sign-out, code email through the outbox, opaque portal sessions pinned to tenant and host (P-08-T10)
spec: SPEC-320
acceptance_criteria: [AC-6, AC-7, AC-8]
risk_zone: red
status: in-progress
epic: P-08
plan_key: P-08-T10
branch: s6-portal-sign-in-bff
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Claire Feld signs in on the staging portal host with a sink-delivered code, an unknown email gets a byte-identical response, and the third wrong code locks sign-in for 15 minutes."

## Plan (red zone)
- **ADR:** ADR-168 (accepted): opaque access tokens checked against `auth_sessions`, pinned to tenant and host; refresh by a `__Host-` cookie with reuse detection, CSRF header and Origin.
- **Migration:** `0116_portal_sign_in.py`: global `sign_in_challenges` and `sign_in_locks` (no app grants), `auth_sessions` portal columns (`surface`, `tenant_id`, `host`, `access_sha256`, `access_expires_at`, provider `portal_code`), nine definers. Rollback: `alembic downgrade 0115`.
- **Registries:** schema_check GLOBAL_TABLES and DEFINER_FUNCTIONS with expectations in `test_schema_check_db.py`; `PRE_SESSION_PATHS` gains `/v1/portal/auth/{start,verify,resend,refresh}`; ADR-152's list.
- **Code:** `identity/portal_session.py` (start, verify, resend, refresh, sign-out, bearer resolution); `identity/portal_auth_routes.py` (the pre-session family, served when `portal.sign_in_v2` is on); `current_context` resolves an opaque portal bearer on its own host; `ClientSignInCodeRequested` outbox event; `communications` delivers the code from the database template `portal.sign_in_code` in the firm's name (issued at delivery: only a salted digest is stored).
- **Rules:** identical 202 for every email (unknown, staff, no grant, another firm's, locked); 10-minute codes; 3 wrong codes lock the (host, email) for 15 minutes; resend after 60 s with tries kept; landing from `portal_scopes`; audit events `portal.sign_in.*` and `session.*` for known people only.
- **Tests:** `tests/integration/test_portal_sign_in.py` (enumeration parity, expiry, lockout, resend, verify to session, refresh rotation and reuse, sign-out); `tests/security/test_portal_host_pinning.py` (another host and the firm host are no session; revoked and expired tokens 401; the token stored only as SHA-256).

## Progress log
- 2026-10-24: plan written; migration 0116 drafted.
- 2026-10-24: built (DEC-212). 8 integration tests pass (`tests/integration/test_portal_sign_in.py`): enumeration parity over HTTP, issue-once, verify to a pinned session, lockout (unknown emails too), expiry and resend, refresh rotation and reuse, CSRF and Origin, token only on its host, sign-out. The contract's `portal.sign_in.*` audit names have two dots; spelt `portal_sign_in.*`. Host-pinning cases live in the integration file for now; `tests/security/test_portal_host_pinning.py` is P-08-T25's. **Open:** the MFA floor (T17) — `portal.sign_in_v2` must stay off in production until then; `/v1/me` portal half (T07); the `portal.sign_in_code` template import per environment (human).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-212 | Delivery-time code issue, lock keying, audit spelling, what waits for T07/T17/T25 | No (ADR-168) |
