---
id: TASK-3343
title: P-11-T25 OCR runs for real, the extraction row and the daily cap
spec: SPEC-000  # row (P-11-T25)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T25
branch: s28r-p11-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Close DEC-2309's partials, and prove a scan reads end to end.

## Plan
- `tests/integration/backfill/test_p11t25_ocr_run.py`: one scan through the real step.
- Fixes from it; `ocr-v1` row; daily cap; migration 0672; history v9. The background class and the backfill were tried and removed (DEC-2332).
- Rollback: revert; `patched` keeps older histories replaying; downgrade 0672.

## Progress log
- 2026-11-06: built. New integration test passes on Postgres and object storage: 2 passed. `tests/unit/evidence`, worker, audit and upload-processing replay suites pass locally.

## Decisions made during this task
DEC-2332
