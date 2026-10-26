---
id: TASK-1293
title: Expand-only migration on audit_events (request context, client and office) and request-context capture into kernel.uow
spec: SPEC-349
acceptance_criteria: [AC-8, AC-9]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T06
branch: s9c-governance
created: 2026-10-26
updated: 2026-10-26
---

## Objective
A person's audit events carry the IP, device, staff session and MFA time of the request behind
them; agent and system events never do; `audit_events` stays insert-only (G-02-T06).

## Plan
- **Migration 0172** (`down_revision = "0160"` on this branch; the merge re-points it after the
  other S9 branches): `audit_events` + `ip inet`, `user_agent_family`, `device_label`,
  `session_id`, `auth_method` (CHECK in sso, email_code, passkey, totp, support, service),
  `mfa_at`, `client_id`, `office_id`; CHECK `audit_events_request_context_is_a_persons`
  (request-context columns null unless `actor_kind IN ('human','support')`); indexes
  `audit_events_feed`, `_actor_kind`, `_client` (partial), `_ip` (partial); the app's insert
  grant widened; definer `audit_request_session(cookie_sha256, user_id)`. Insert-only triggers,
  RLS and the human-only guard are untouched (the `abacus_human_only_actions()` register is not
  changed).
- **Hash chain leaf v2** (`kernel/uow/chain.py`, Q-02 R7): seals at version 2 with the new
  columns; a version 1 checkpoint keeps verifying with version 1's columns.
- **Capture**: `kernel/request_context.py` (context, closed-list device labels, the cookie kept
  only as its SHA-256, a session-resolver slot); `api/request_context.py` (ASGI, inside the
  proxy-header middleware); `identity/request_session.py` registers the resolver over the
  definer; `identity/routing.current_context` notes the MFA time (staff), the portal session and
  `email_code` (portal), and `support` (support engineers). `UnitOfWork._write` writes the
  context for human and support contexts only.
- **Classification**: `ip` and `device_label` are Confidential personal data, never logged; the
  others Internal (SPEC-349 §7, the contract's models).
- `APP_INSERT_COLUMNS` (schema_check `_PLATFORM_INSERT_COLUMNS`), `DEFINER_FUNCTIONS` and its
  test set.
- **Tests**: `tests/integration/test_g02t06_audit_request_context.py`,
  `tests/unit/kernel/test_g02t06_request_context.py`; `test_audit_chain.py`'s R7 check now reads
  the current leaf version.
- **Rollback**: `alembic downgrade 0160` (local only) drops the function, indexes, CHECK and
  columns and restores the grant; revert the code. Checkpoints sealed at version 2 would no
  longer verify after a downgrade, so production never downgrades this (forward-fix).

## Progress log
- 2026-10-26: built. up/down/up of 0172 runs on a private local test database
  (`test_migration_0172_goes_up_down_and_up`, plus the session database's full roundtrip); the
  staging-copy run in the acceptance line is a deploy step. 61 audit and chain integration tests,
  12 unit tests, the schema_check definer and grant tests (180) and AC suite 1 green.
- Decisions: DEC-418. `auth_method` stays null for staff BFF sessions until the sign-in method is
  stored on the session (G-02-T14, SPEC-349 Q7); `client_id` and `office_id` are columns only
  here, callers fill them from G-02-T08.
