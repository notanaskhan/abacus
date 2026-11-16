---
id: TASK-8087
title: "A-08-T33: ADR-078 independent AC tests for the T09 GL JE fields"
spec: SPEC-657
acceptance_criteria: [AC-0, AC-1]
risk_zone: red
status: in-review
branch: a08-t33-je-fields-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T33
---

## Objective
Independent tests (ADR-078) for A-08-T09, written from the spec: the migration is expand-only,
each format's column map is sound, the unavailable path names what is missing, and no posting
user or approver value reaches a log line or an error.

## Built
- `tests/unit/ledger/test_a08t33_je_fields_independent.py` (12 pass): the 0888 upgrade parsed by
  AST (only ALTER TABLE ... ADD COLUMN NULL/DEFAULT and GRANT; no UPDATE, DELETE, DROP, TYPE,
  SET NOT NULL, RENAME); the downgrade drops exactly the five columns; per-format maps (each JE
  field once, never onto a base column; one format carries all four, one none); the unavailable
  path (`manual_by_role` names `posted_by`, `source`; the others need nothing extra; an
  unavailable criterion hits nothing); a sentinel posting user and approver never appear in
  structlog output, stdout/stderr, stdlib logs or a scoring error.
- `tests/integration/test_a08t33_je_fields_independent.py` (Postgres; end pass): an earlier
  snapshot reads every JE field unavailable; neither the owner nor the app can fill a JE field on
  a committed row (ADR-004 triggers and grants).
- Also: typing fixes on TASK-8086's tests (policy literal, CRITERIA annotation).

## Progress log
- `2026-11-15` — Built; unit file passes, integration file runs in the end pass.
