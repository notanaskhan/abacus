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

- 2026-10-26: one targeted pass at the end of the wave (brief step 7): 1,520 backend tests in the
  touched and covering files (unit integrations, assurance, ledger, workpapers ties, audit
  targets, release and deploy workflows; C9 and C20 contract suites; the three new schema files,
  test_tb_versions, test_schema_check_db, test_retrieval; security a02t10, c09 authz, route
  introspection, tenant isolation, audit targets): 5 failed, fixed, re-run green (expected-map
  and consumer 501 updates; the a02t10 test now turns on `g2_blocks_view` on an attest
  engagement, since G2 binds reads only there, ADR-164; fieldwork registers the adjustment
  source, so all four layers exist in the app). Vitest AUD-06, AUD-02, C9 and C20 fixture
  contracts: 73 passed. Gates: ruff format/check, pyright, lint-imports, banned_patterns,
  error_codes, validate_docs, scope_guards, fresh_mfa, secrets_scan, check-heads,
  check-generated; tsc, eslint, prettier on touched files. Playwright not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-437 | The issue link lives on `tie_out_checks` (plan §4.2), set once by column grant; the balanced rule is a trigger because `kind` and `expected` are on different tables | No |
