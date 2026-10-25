---
id: TASK-1201
title: Compliance-kernel v1.1 contract stub for G-02 and Q-05 - the firm-export family, the live incident, retention and hold halves indexed, seed-derived fixtures (Q-02-T38)
spec: SPEC-050
acceptance_criteria: [AC-21]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T38
branch: s8a-identity-security
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"G-02's consumer contract tests run green against the stub" (Q-02-T38): incident create with clock fields, firm-export request, approve and link, retention policies read, legal holds read; seed-derived fixtures (INC-2026-005 day 4 of 30, export Waiting for approval by Margaret Okonkwo); make generate; compliance-kernel contract v1.1. (SPEC-050 AC-21 is the contract-stub handshake the task schema needs; Q-02's own SPEC is not written.)

## Plan (red zone: contract)
- **Already live on the base** (indexed, not changed): `POST /v1/firm/security/incidents` with `ftc_notify_by`, `clock_day`, `clock_days`, `notification_event` (Q-02-T33, migration 0143); `GET /v1/retention/policies`; `GET /v1/legal-holds`.
- **New stub:** `evidence/firm_export_contract.py`: `GET` and `POST /v1/firm/data-exports`, `POST …/{export_id}/approve`, `/decline`, `/link`, with classified models (`FirmExportOut`, `FirmExportPageOut`, `FirmExportRequestIn`, `FirmExportDeclineIn`, `FirmExportLinkOut`, `FirmExportPersonOut`), behind `compliance.firm_export` (404 off, 501 on). Matrix rows existed (Q-02-T30); the request takes an `Idempotency-Key` and answers 202. The shared 410 description is generalised (it named only sign-in codes).
- **Closed lists:** `tests/unit/api/test_app_gates.py` (the request is 202; approve, decline and link create nothing); `make regenerate` (route introspection, fresh-MFA overlay, OpenAPI, client).
- **Fixtures:** `apps/web/src/fixtures/seed/compliance.ts`, `handlers/compliance.ts`, `contracts/compliance-kernel.contract.test.ts`; backend `tests/contracts/compliance_kernel/` (stub and consumers).
- **Docs:** `docs/contracts/compliance-kernel.md` v1.1 and its register row.
- **Rollback:** revert the commit and regenerate.

## Progress log
- 2026-10-25: built. `tests/contracts/compliance_kernel` 24 passed; vitest `compliance-kernel.contract.test.ts` 5 passed; tsc and eslint clean.
- Not here: the firm-export status words (G-02-T11 registers them with the card); the monthly schedule (G-02-T19); the implementation (Q-02-T43). The ADM-06 handoff gives INC-2026-005's title ("Credential-stuffing attempts against client portal sign-in") and the 2:14 AM discovery; the scheduled exports' `expired` status is inferred from the 7-day window at E0, and their manifest digests are placeholders until an archive exists.

- 2026-10-25 (verification, branch tip): `pytest tests/unit tests/contracts tests/security` 28638 passed, 4 xfailed; integration `test_portal_sign_in`, `test_portal_mfa`, `test_portal_invitations`, `test_staff_session`, `test_security_incidents`, `test_portal_recovery`, `test_db_tls`, `test_uow_session_rollback`, `test_platform_tenancy`, `test_p08t20_portal_sign_in_independent`, `test_scenario_portal`, `test_portal_branding`, backfill `test_contacts_access`, `test_client_invitations`, `test_p07t26_contacts_g2_independent`: 212 passed, 3 xfailed; `test_schema_check_db` 192 passed; `make check-fast` green; vitest POR-01, fixtures, status, portal domain, app-core 543 passed.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-331 | The firm-export stub's shapes, statuses and errors | No |
