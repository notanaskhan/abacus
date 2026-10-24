---
id: TASK-1199
title: Secure links and recovery - migration 0156 secure_links, issue and resolve, link renewal to the original address, firm-side unlock and MFA reset, the per-firm sign-in pause (P-08-T21)
spec: SPEC-320
acceptance_criteria: [AC-14, AC-18, AC-19, AC-20]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T21
branch: s8a-identity-security
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"An expired reminder link renews to the same address with an identical response for any token, unlock and reset deny the agent principal, and the pause takes effect within 10 seconds." Bound by ADR-168 (host-pinned portal sessions), the MFA floor (P-08-T17, DEC-250) and invitations v2's guarantees (DEC-275, DEC-277); links single use and kept as hashes only; one 404 for every bad link.

## Plan (red zone: identity, communications, migration)
- **Migration 0156** (`down_revision` 0146): `secure_links` (communications, tenant, forced RLS; insert columns; update only `token_sha256` and `revoked_at`); definers `portal_host_tenant`, `portal_link_claim`, `portal_link_renew`, `portal_invitation_find`, `portal_mfa_reset`, `portal_mfa_unlock`; `client_invitations.renewal_count` updatable; ADR-157's one spelling (`portal_sign_in_disabled` → `portal_sign_in`; the insert-only history keeps both). Rollback: `alembic downgrade 0146`.
- **Kernel:** `kernel/controls.py` `control_active` (the one reader of `platform_control_state()`, 10 s cache, fail-closed for `ai_pause` and `read_only`), re-exported as `platform.api.control_active`.
- **Identity:** `portal_session.check_not_paused` (503 `sign_in_paused` on start, verify, resend, mfa, mfa/setup, mfa/setup/verify; refresh and sessions untouched); `start_sign_in(link_token=…)` through the new `slots.register_link_claim` (404 `link_expired` for every bad link); `portal_recovery.py` (`reset_portal_mfa`, `unlock_portal_mfa`, `remove_provider_factor`, `renew_invitation`); `PortalMfaResetNoticeRequested`; the firm-side stub routes leave `portal_contract.py`.
- **Organisations:** `POST /v1/clients/{client_id}/contacts/{contact_id}/portal-unlock` and `/mfa-reset` (behind `portal.sign_in_v2`, idempotent reset authorised before the replay lookup); CLI-04's `/v1/contacts/{id}/unlock` also clears the second-step lock.
- **Communications:** `secure_links.py` (`issue_secure_link`, `resolve_secure_link`, `claim`, `renew_link`, `deliver_renewed_link`), `secure_link_routes.py` (`POST /v1/portal/links/renew`, pre-session), `deliver_mfa_reset_notice`.
- **Registries and closed lists:** communications `registry.py`, identity `registry.py` (`renewal_count`), `schema_check.py` definers and `test_schema_check_db.py`, `audit_trail/targets.py` (`secure_link`), `PRE_SESSION_PATHS`, `PUBLIC_ROUTE_EXCEPTIONS`, `test_app_gates.py`, `test_routing.py`, `test_worker_screening.py`, the C5 portal stub test, `fresh-mfa-actions.yaml` (`contact.mfa_reset`), `make regenerate`.
- **Frontend:** the start fixture answers 404 `link_expired`; the renew types are generated.
- **Tests:** `tests/integration/test_portal_recovery.py` (10 cases).

## Progress log
- 2026-10-25: built and green. `test_portal_recovery.py` 10 passed; see the report for the other suites.
- **Not here (follow-ups):** R-01 calls `issue_secure_link` from its POR-20 emails, and the invitation email moving onto secure links (the epic's §4.1 line) waits for it; the C16 templates `portal.link_renewed` and `portal.mfa_reset_notice` must be imported per environment (human to-do, as `portal.sign_in_code`); `portal_mfa.reset` is not on the database human-only register (the matrix, `_human` and the route's fresh MFA hold it; adding it needs a migration redefining `abacus_human_only_actions()` from main's list); the operator CLI `abacus_tools.platform_control` (ADR-157) still doesn't exist: a pause is set with `set_platform_control` as `abacus_ops`; IP and device in these audit rows (DEC-60) as for T10.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-329 | The link, renewal, recovery and pause rules as built | No (ADR-157 proposed: its one spelling applied) |
