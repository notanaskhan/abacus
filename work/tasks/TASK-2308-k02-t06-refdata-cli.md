---
id: TASK-2308
title: K-02-T06 reference-set operator CLI
spec: SPEC-500
acceptance_criteria: [AC-35, AC-36, AC-37, AC-38]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T06
branch: s18-k02-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Operator CLI abacus_tools/refdata.py (make refdata-draft, refdata-diff, refdata-publish,
refdata-withdraw): hostile CSV/XLSX parse on the workbook.py pattern, row-level diff against the
current version, two-person publish with a reason, refusal while a hosted deploy holds the
database, ECS one-off task for staging and production. Acceptance (row): the founder who drafted
a version cannot publish it, formula cells are read as cached values only, and the diff lists
every changed row.

## Plan
- `abacus_tools/refdata.py`, Makefile targets, SPEC-500 AC-35 to AC-38, DEC-1355.
- Tests: `tests/unit/tools/test_k02t06_refdata_cli.py` (no database).
- Rollback: revert.

## Progress log
- `2026-10-30` — built. Tests written, not yet run (S18 end review; `[skip ci]`).

## Handoff
- **Current state:** built, PR open, held for the S18 batch.
- **Exact next step:** K-02-T10 standards API.
