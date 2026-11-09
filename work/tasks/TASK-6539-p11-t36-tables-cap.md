---
id: TASK-6539
title: "P-11-T36 finish: TABLES reads within the daily cap; none for intake attachments"
spec: SPEC-029
acceptance_criteria: [AC-1]  # the daily cap holds for every billed page
risk_zone: amber
status: in-review
branch: s33r-p11-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-10
updated: 2026-11-10
plan_key: P-11-T36
---

## Objective
The TABLES pass never takes a firm past its daily page cap, and an intake attachment pays for no
TABLES read (its filed evidence version is read on its own).

## Plan (amber)
- `evidence/ocr_step._read`: the statement pages are counted with the pages just read before
  any TABLES read is sent; over the cap, none is sent and an `analyze_tables` run is recorded
  refused (`quota_exceeded`); an intake attachment's pages are never TABLES candidates.
- Test `tests/unit/evidence/test_s33r_p11t36_tables_cap.py`.
Rollback: revert.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3139 | TABLES pages count against the cap before they are sent; intake reads none | no |
