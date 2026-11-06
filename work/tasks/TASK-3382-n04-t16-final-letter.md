---
id: TASK-3382
title: N-04-T16 final letter and paid date
spec: SPEC-000  # row (N-04-T16)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T16
branch: s28p-n04-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
DEC-2376's partials that can close now.

## Plan
- `notices/sending.py` finalises the letter before the envelope; `paid_on` on acceptance. No migration.
- Rollback: revert.

## Progress log
- 2026-11-06: built. `tests/integration/test_n04t16_final_letter.py`, `tests/unit/notices/test_n04t16_sending.py`. See DEC-2381 for what stays open.

## Decisions made during this task
DEC-2381
