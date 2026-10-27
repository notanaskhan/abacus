---
id: TASK-1503
title: P-07-T52 CLI-06 bulk client and contact import, live
spec: SPEC-332
acceptance_criteria: [AC-24]  # walled clients are never a match; Story 3.2 is the epic AC
epic: P-07
risk_zone: amber
status: in-review
branch: s12b-p07t52
created: 2026-10-27
updated: 2026-10-27
---

## Objective
The client-import routes go live: upload, score, decide, run through `ClientImportWorkflow`, 30-day file retention (DEC-643).

## Plan (amber)
- **Migration** `0250_client_imports.py` (down 0244; renumber on rebase): `client_imports`, `client_import_rows` (forced RLS, column grants, applied-row trigger), `client_import_files_erase()` (SECURITY DEFINER, count only). Rollback: `downgrade()` drops both tables and both functions (synthetic data only).
- **Code** (engagements): `client_import_parse.py` (headings, inert cells, TIN kinds), `client_import.py` (service, row apply, erase), `workflows.py` (`ClientImport`, `ClientImportErase`), `client_import_activities.py` (activities, work classes, the platform Schedule `client_import_erase:platform`); `api.py` now declares `SUBSCRIPTIONS` (empty), `WORKFLOWS`, `ACTIVITIES`, `SCHEDULES`. Live routes in `intake_contract.py`.
- **Organisations**: `ein_matches` (EIN fingerprint match, walls applied), `fingerprint_tin` exported, `seal_tin` accepts `client_import.run`.
- **Registry**: both tables, insert and update columns. Activity review list: seven `client_import.*` actions. Outbox: `client_import.completed`.
- **Tests (written, run in the S12 batch pass)**: `tests/unit/engagements/test_p07t52_import_parse.py`, `tests/integration/backfill/test_p07t52_client_import.py`; contract stub and consumer suites moved from the 501 stub to live; `test_platform_schedules.py` lists the new Schedule.
- **Still to do in the batch pass**: record a `ClientImport` replay history (ADR-090) once the workflow runs against the dev Temporal; P-07-T51's independent suite (notanaskhan) must pass unchanged.

## Progress log
- 2026-10-27: built per the plan; lint and pyright clean on the changed files; `make regenerate` run. Tests not run (S12 batch: one test pass at the end).
