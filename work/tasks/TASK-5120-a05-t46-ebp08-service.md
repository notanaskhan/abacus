---
id: TASK-5120
title: A-05-T46 EBP-08 service: rollforward, SDBA, vesting and the Begin run
spec: SPEC-000  # row (A-05-T46)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T46
branch: s29-a05-t46
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Participant accounts from stored rows: crossfoot, foot, transfers net to zero, ties, SDBA by type, vesting of the plan year's terminations, and a person's Begin run.

## Plan
compute/ebp/accounts.py; assurance/ebp_accounts.py; ebp_contract.py routes (rollforward now live, groups, sdba, vesting, run); regenerate. Replaces the literal stub's FiguresOut.

## Progress log
- 2026-11-06: built. `backend/tests/unit/assurance/test_a05t46_accounts.py` (goldens) written, not run (end pass). Pyright, ruff, banned patterns clean.

## Decisions made during this task
DEC-2416
