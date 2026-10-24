---
id: TASK-1101
title: Audits family contract stub - models, routes, slots, matrix rows, audits.cockpit flag (A-01-T02)
spec: SPEC-330
acceptance_criteria: [AC-3, AC-4, AC-5, AC-6, AC-7]
risk_zone: red
status: done
epic: A-01
plan_key: A-01-T02
branch: s7-a01-audit-wedge
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The stub merges in the Tue Jan 26 train with the flag off and generated client types, and the contract doc lists every human-only action and audit event."

## Plan (red zone)
- **Code:** `assurance/audits_contract.py` (models with `classified(...)`; seven routes, one action each, `_stub` = 404 off / 501 on), `assurance/sections.py` (three slots), `assurance/api.py` (router, slot exports, A-01's three segments); `requests/contract.py` C5 v1.1 optional row fields, exported through `requests/api.py`.
- **Matrix:** `permission-matrix/assurance.yaml` + `assurance.record_phase`, `assurance.record_release`, `assurance.record_archive` (human only, independence; MFA on release and archive).
- **Flag:** `feature-flags/assurance.yaml` `audits.cockpit` (boolean, off, expires 2027-04-21, DEC-137).
- **Regenerate:** `make regenerate` (matrix, flags, OpenAPI, client, route introspection and matrix cases).
- **Closed lists:** `test_app_gates.py` (the three record routes create, 201), `test_independence.py` (three marked actions).
- **Tests:** `tests/contracts/audits/test_audits_stub.py`, `tests/unit/assurance/test_audit_sections.py`.
- **Docs:** `docs/contracts/audits-cockpit.md`, register row in `docs/contracts/README.md`, DEC-261.
- **Rollback:** revert the commit and `make regenerate`; the flag is off and no table changes.

## Progress log
- 2026-10-24: built. `tests/contracts/audits` + slot unit tests 50 passed; matrix, route introspection, app gates, independence, status vocabulary and C5 suites green (8258 passed). P-06's A-01 consumer test pinned `BinderRequestRowOut`'s confidential fields, so the new wrappers are internal with confidential `display` and `path_label`.

- 2026-10-24: security review: each stub now authorises its action (client, agent and system 403; work item through `authorise`) before the flag or 501 (`tests/unit/assurance/test_audits_review.py`); C5 v1.1 row fields firm-only (`requests.contract.for_viewer`). DEC-261 amended.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-261 | Slot shapes, index action, record actions, C5 v1.1 optional fields | No |
