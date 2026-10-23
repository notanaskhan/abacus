---
id: TASK-958
title: C4 stub — citations v2, viewer, regions, search, PII reveal and unlock routes; evidence matrix and flags; make generate (P-03-T02)
spec: SPEC-322
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T02
branch: s5-trust-kit
created: 2026-10-23
updated: 2026-10-23
---

## Objective
Contract-first stub for the C4 family (`docs/contracts/c04-citations-viewer.md`): every route answers 404 with its flag off and 501 `not_implemented` with it on, and its models carry classification tags.

## Plan (red zone)
- **Files:** `backend/src/abacus/modules/evidence/trust_contract.py` (new; router mounted from `evidence/api.py`); `docs/architecture/permission-matrix/evidence.yaml` (`citation.read`, `citation.create`, `citation.relink`, `pii.reveal`, `evidence.unlock`); `docs/architecture/feature-flags/evidence.yaml` (`evidence.citations_v2`, `evidence.viewer_v1`, `evidence.pii_reveal`, `evidence.viewer_unlock`); `docs/product/status-vocabulary.yaml` (citation, viewer, evidence_unlock).
- **Generated:** `make regenerate`, `make generate` (matrix, flags, statuses, OpenAPI client, actions).
- **Test lists:** `test_app_gates` (created and NOT_CREATING), `test_independence` MARKED, status vocabulary xfails retired where now passing, route introspection, tenant isolation, matrix generated.
- **Rollback:** revert the commit; no data.

## Progress log
- 2026-10-23: built. `pii.reveal` requires `not_offshore`, independence and `mfa_recent`; support has no entry (support stays read-only). `EvidenceUnlockIn.password` is a `SecretStr` and never logged. Shipped in one batch PR with P-03-T03 and P-03-T04.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| One flag per route family | DEC-148 | no |
