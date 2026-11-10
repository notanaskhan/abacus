---
id: TASK-3306
title: "A-05-T39 EBP-06 service: trust agreement, layers and the certification hold"
spec: SPEC-000  # row (A-05-T39)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T39
branch: s28-a05-t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"Six funds foot to 14,895,000 and 12,683,000, the Unadjusted layer shows a 0.00 receivable and 16,812,400, and Sign off answers 409 certification_unevaluated until every point is evaluated."

## Plan
- `assurance/compute/ebp/trust_agreement.py`: pure agreement by line, footing by level.
- `assurance/ebp_investments.py`: lines by layer from the ledger, certification points and evaluations, sign-off guard.
- `GET /ebp/investments` returns `InvestmentsOut`; `GET /ebp/certification`; `PUT …/points/{key}` live.
- Rollback: restore the stubs; no schema.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2305
