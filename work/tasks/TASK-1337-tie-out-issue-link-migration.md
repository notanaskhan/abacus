---
id: TASK-1337
title: tie_out_checks issue link and the remaining A-02 §4.2 rules, migration 0193 (A-02-T11)
spec: SPEC-333
acceptance_criteria: [AC-10]
risk_zone: amber
status: in-review
epic: A-02
plan_key: A-02-T11
branch: s10b-ledger-integrations
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The migration passes up/down/up and a version row with an expected value but no citation id is
refused by CHECK."

0074 (SPEC-310, TASK-321) already built `tie_out_checks` and the insert-only
`tie_out_check_versions` with the citation and human-only CHECKs. Left from the row: the issue
link, the balanced-has-no-expected rule and the immutability trigger of A-02 §4.2's "IO".

## Plan
- Migration `0193_tie_out_issue_link.py` (`down_revision = "0172"`; the merge re-points it):
  `tie_out_checks.issue_id`, `issue_linked_by`, `issue_linked_at` (all or none; composite FK to
  `issues`; UPDATE granted on these three only); BEFORE INSERT trigger
  `tie_out_check_versions_rules` (a `balanced` check's version has no expected value);
  `tie_out_check_versions_immutable()` BEFORE UPDATE OR DELETE and TRUNCATE triggers.
- Registry: `workpapers/registry.py` UPDATE_COLUMNS; `tie_models.py` columns.
- `schema_check.IMMUTABLE_TABLES` and the expected map in `test_schema_check_db.py`.
- Tests: `backend/tests/integration/test_tie_out_schema.py` (up/down/up with a row in place, the
  citation CHECK as the app role, balanced-without-expected, human only, no UPDATE/DELETE for any
  role, the issue link whole and in the firm). DB-001 exclusion for the file.
- Rollback: downgrade drops the triggers, functions, grant and columns (no data in them yet).

## Progress log
- 2026-10-26: plan written; built with the rest of S10 wave B (tests at the end, brief step 7).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-437 | The issue link lives on `tie_out_checks` (plan §4.2), set once by column grant; the balanced rule is a trigger because `kind` and `expected` are on different tables | No |
