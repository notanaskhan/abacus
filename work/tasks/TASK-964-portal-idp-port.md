---
id: TASK-964
title: WorkOS portal adapter port — user upsert, TOTP enrol, challenge and verify; own email codes; contract tests (P-08-T06)
spec: SPEC-320
acceptance_criteria: [AC-2]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T06
branch: s5-portal-idp
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The same contract tests pass against WorkOS staging and the local fake, and no code path sends a WorkOS-branded email to a client."

## Plan (red zone)
- **Code:** `identity/portal_idp.py` — the `PortalIdp` port, `WorkOsPortalIdp` (SDK in a thread; errors become `PortalIdpUnavailable` with the type only), `InMemoryPortalIdp` (RFC 6238), own email codes (`issue_email_code`, `email_code_matches`), `check_issuer`.
- **Config:** `workos_api_key` (Restricted, SecretStr) and `workos_client_id`; not added to the staging adapter list, so a deployed process without them fails closed at sign-in rather than at boot.
- **Allowlist:** `workos: approved` already (Q-01-T05). No new dependency.
- **Tests:** `tests/contracts/portal_idp/test_portal_idp_contract.py` — the port's contract on each provider (WorkOS staging behind `ABACUS_TEST_WORKOS_API_KEY`), RFC 6238 vectors, single use and drift, email code hashing, the issuer guard, and a scan that nothing calls Magic Auth.
- **Rollback:** revert the commit; no data.

## Progress log
- 2026-10-23: built. Own-OTP fallback taken (DEC-155): the SDK's Magic Auth always sends WorkOS's email. The challenge table and the SES send are P-08-T10's. The WorkOS staging run is skipped here: no staging credentials in this environment.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-155 | own email codes; WorkOS for users and TOTP | no (P-08 R1 names the fallback) |
