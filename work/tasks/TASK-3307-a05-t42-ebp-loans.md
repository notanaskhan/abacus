---
id: TASK-3307
title: A-05-T42 EBP-05 service: loan rollforward, 72(p) limit, withholding and offsets
spec: SPEC-000  # row (A-05-T42)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T42
branch: s28-a05-t42
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"The rollforward foots to 312,400 with 36 loans, offsets total 14,850, and Part IV 4b answers No because participant loans are excluded."

## Plan
- `assurance/compute/ebp/loans.py`: rollforward, IRC 72(p), withholding, offsets, PY comparative.
- `assurance/ebp_loans.py`: reads over 0667.
- Routes: `GET /ebp/loans/rollforward`, `/new`, `/offsets`, `/participants/{key}/loan`.
- The distributions test is the shared grid on A-03's second sample set (no new route).
- Rollback: restore the stub; no schema.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2306
