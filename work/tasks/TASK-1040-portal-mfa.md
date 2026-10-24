---
id: TASK-1040
title: Portal MFA — migration 0133, the MFA floor slot failing closed, TOTP enrol and verify, 8 backup codes, 30-day trusted devices, stricter-only firm extension, revocation on access.changed (P-08-T17)
spec: SPEC-320
acceptance_criteria: [AC-10, AC-11]
risk_zone: red
status: in-progress
epic: P-08
plan_key: P-08-T17
branch: s7-p08-t17-portal-mfa
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Tess Moreno cannot finish sign-in without a second factor, Claire Feld is not asked for one before the TRI predicate exists, and a raising predicate makes MFA required."

## Plan (red zone)
- **ADRs:** ADR-168 (the portal session this extends: "when the client's role needs MFA"), ADR-146 and DEC-34 (the floor), DEC-35 (15-minute lock, 30-day devices), DEC-63 (designations), DEC-60 (identifiers only in audit), DEC-212 (the sign-in core).
- **Migration `0133_portal_mfa.py`** (down_revision = head on origin/main at start, 0116; the main session re-chains):
  - **New, global, definers only** (no app privileges, as 0116): `mfa_factors` (the WorkOS factor per user: provider user and factor ids, `enrolled_at` null while setup is pending; a factor belongs to the person, ADR-002), `mfa_backup_codes` (SHA-256 of 80-bit codes, `used_at`), `trusted_devices` (tenant, user, SHA-256 of the device cookie, `expires_at`, `revoked_at`, `revoked_reason`, `ua_family`).
  - **New, tenant** (forced RLS, app `SELECT` only; G-02 adds the writer): `portal_security_policies` (`mfa_for_all_client_users` default false, `trusted_device_days` default 30, `CHECK BETWEEN 0 AND 30`, `version`, `updated_by`, `updated_at`). Stricter-only by shape: the only switch widens the floor, and the day count can only shorten the 30-day ceiling.
  - **Alter** `sign_in_challenges`: the second-step token (`mfa_token_sha256` unique, `mfa_kind` `verify|setup`, `mfa_expires_at` 5 minutes, `mfa_setup_at`, `mfa_used_at`); `sign_in_locks`: `mfa_attempts`, `mfa_window_until` (second-step guesses counted apart from code guesses and not reset by a right email code; the third wrong one sets the same `locked_until`).
  - **Definers:** `portal_mfa_begin`, `portal_mfa_attempt` (counts before compare, under row locks, like `portal_sign_in_attempt`), `portal_mfa_missed`, `portal_mfa_backup_use`, `portal_mfa_setup_claim`, `portal_mfa_factor_pending`, `portal_mfa_enrol`, `portal_mfa_complete`, `portal_mfa_enrolled`, `portal_session_mark_mfa`, `portal_device_trust`, `portal_device_check`, `portal_access_revoke`.
  - Rollback: `alembic downgrade 0116` (drops the four tables, the columns and the definers).
- **Registries:** `identity/registry.py` TABLES; `schema_check.py` GLOBAL_TABLES, NON_TENANT_TABLES and DEFINER_FUNCTIONS, with expectations in `tests/integration/test_schema_check_db.py`; `PRE_SESSION_PATHS` and `banned_patterns.PUBLIC_ROUTE_EXCEPTIONS` gain `/v1/portal/auth/{mfa,mfa/setup,mfa/setup/verify}` (ADR-168 already names the second step as part of the pre-session family); route introspection and 200-POST lists; identity `SUBSCRIPTIONS` consume `access.changed` and `client_access.revoked`.
- **Code:**
  - `identity/mfa.py`: `register_mfa_requirement(name, predicate)`; `mfa_required(tenant, user)` — true when the firm policy says every client user, or any predicate is true, raises or takes over 2 s, or a floor predicate (`owner_grant`, `engagement_designation`) is not registered (fail closed). The second step, setup, backup codes, trusted devices and revocation.
  - identity registers `owner_grant` (an active `owner` grant); engagements registers `engagement_designation` (`approver_of_record`, `signing_officer`, `ske_designee` on any of the person's contacts, read through `organisations.api`).
  - `portal_session.verify_code`: after the code matches, a person the floor covers gets `mfa_required` (factor enrolled; skipped by a live trusted device for this firm) or `mfa_setup_required` (no factor) with a 5-minute single-use `mfa_token`, and no session.
  - Routes `POST /v1/portal/auth/mfa`, `/mfa/setup`, `/mfa/setup/verify` (contract shapes as stubbed): 401 `mfa_mismatch {tries_left}`, 423 `mfa_locked {locked_until}`, 410 `mfa_expired`, 503 `mfa_unavailable`. Trusted device cookie `__Host-abacus-portal-device`.
  - `/v1/me.mfa` filled for a client membership (`enrolled`, `required`).
  - Audit (one dot, DEC-212's spelling): `portal_mfa.enrolled`, `portal_mfa.verified`, `portal_mfa.failed`, `portal_mfa.locked`, `portal_backup_code.used`, `portal_device.trusted`, `portal_device.revoked`, `session.started`, `session.ended` (reason revoked).
- **Rules:** setup only for a person with no enrolled factor and only once per token (the secret is shown once); 8 backup codes shown once, stored as SHA-256, each usable once; three wrong second-step codes lock for 15 minutes; a trusted device lasts the firm's days (≤ 30, 0 = never trusted), checked against the current policy on every use, and is revoked with the person's access; nothing Restricted is logged, audited or returned twice.
- **Tests (acceptance first):** `tests/integration/test_portal_mfa.py` (Tess owner, Claire taxpayer, raising and slow predicates, designation, firm extension, setup once, backup single use, lock, trusted device expiry and policy shortening, revocation on `access.changed`, single-use token, counting before compare under parallel guesses); `tests/unit/identity/test_mfa_floor.py` (slot fail-closed rules). `test_portal_sign_in.py`'s fixture person moves from `owner` to `contributor` (an owner now needs the second step; that path is covered here).

## Progress log
- 2026-10-24: plan written.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-250 | MFA floor slot, second-step storage and lock keying, trusted devices, revocation, what waits for T21/G-02/T-01 | No (ADR-168, ADR-146) |
