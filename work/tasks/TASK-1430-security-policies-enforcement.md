---
id: TASK-1430
title: Security policies and their enforcement (G-02-T14; ADM-06 identity half)
spec: SPEC-349
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-26, AC-28, AC-29, AC-30, AC-45, AC-46, AC-47]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T14
branch: s11-security
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Make identity's half of the security center live (`docs/contracts/security-center.md`): the
firm's sign-in policy, the SSO-exempt account, the portal session length, sessions and per-firm
sign-out, unlock, the support switch, residency and posture; and enforce them in the BFF. The
independent suite `tests/integration/test_g02t12_security_center_ac_suite.py` (G-02-T12) is the
definition of done: its identity routes move from STUBBED to LIVE.

## Plan
- **Migration 0220** (`down_revision` 0197; the batch re-points it): `security_policies` (forced
  RLS, a live person's own by trigger, CHECKs hold the platform maxima and floors, the exempt
  account a member and never self-designated, the "last tested" stamp the database's);
  `portal_security_policies.portal_session_minutes` (15 to 480) with G-02's writer for that column
  only; `auth_session_tenant_revocations` (forced RLS, insert-only, a person's act);
  `auth_sessions.auth_method`; definers `auth_session_start`/`auth_session_rotate` overloads
  (method; limits from the BFF), `auth_session_owner`, `security_sessions`,
  `security_session_member`, `security_sign_in_methods` (the session's firm only),
  `auth_session_signed_out` (one boolean about the caller's session), `auth_session_purge`.
- **Service** `identity/security_policies.py`; routes in `security_center_contract.py` (matrix,
  then the flag, then the service). Errors: `session_limit_out_of_range`, `sso_exempt_not_self`
  added (catalogue rewritten with `error_codes --write`).
- **BFF** (`staff_session.py`): strictest limits of the person's firms at sign-in and refresh;
  Require SSO refuses other methods (exempt account: passkey only); exempt sign-in stamps
  "last tested". `routing.current_context` refuses a session signed out of the chosen firm (401).
- **Support** (`support.py`): `require_support_requests_allowed` in SPEC-012's request transaction.
- **Portal** (`portal_session.py`): new portal sessions last the firm's portal length (8 h max).
- **Posture**: `register_posture_source`; platform registers open incidents.
- **Audit**: catalogue entries for the contract's action names; `security_policy` and
  `portal_security_policy` value resolvers (refs only) in platform; both firm-level targets.
- **Purge**: `AuthSessionPurgeWorkflow` on Schedule `auth_session_purge:platform` (daily), replay
  history recorded, the Schedule exact lists updated.
- **Registries**: identity registry (tables, insert-only, insert/update columns), schema_check
  definers, `test_schema_check_db` update columns, generated tenant-isolation list.
- **Tests**: the G-02-T12 suite (identity routes LIVE; AC-30 posture assertion per DEC-530), the
  stub contract test (identity routes live, `_gate`), `tests/integration/test_g02t14_security_policies.py`
  (BFF limits, SSO refusal, per-firm sign-out at request time, portal length, purge, resolvers).
- **Rollback**: revert the commits and downgrade 0220 (drops the new tables, column and
  definers; 0101's functions are untouched). Flag `security_center.v1` stays off for real firms.

## Progress log
- 2026-10-27: planned and built. Decisions DEC-524 to DEC-531.
