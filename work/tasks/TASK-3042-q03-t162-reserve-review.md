---
id: TASK-3042
title: Q-03-T162 quarterly reserve review 2027 Q3
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # the review is recorded in the capacity ledger and the next quarter's lanes are re-sized
risk_zone: green
status: done
epic: Q-03
plan_key: Q-03-T162
branch: s25-q03-t162
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"The review is recorded in the capacity ledger and the next quarter's lanes are re-sized."

## Plan (green)
- `docs/quality/reserve-review-2027-q3.md`: burn by workstream (S19-S25), the escaped-defect retro
  by layer, 2027 Q4's lanes re-sized.
- `docs/product/capacity-ledger.md`: the review's section.
- Rollback: revert. Docs only.

## Result
9.75 of 65.75 te burned (merged or in review); Q4's integration, escaped-defect and catch-up lanes
kept; window hardening held until a live firm; pen tests deferred; load, drills and SOC 2 wait on
environments.

## Progress log
- 2026-11-03: built.

## Decisions made during this task
None (DEC-1389 and DEC-2081 apply).
