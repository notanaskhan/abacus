---
id: TASK-6321
title: T-04-T06 RW-1 and WS-1 consumer contract tests
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: T-04
plan_key: T-04-T06
branch: s32-t04-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s32
created: 2026-11-09
updated: 2026-11-09
---

## Objective
Consumer suites that fail if a field an artboard needs is removed, and that hold the figures.

## Progress log
- `2026-11-09` — `backend/tests/contracts/tax_workspace/test_rw1_ws1_consumers.py` written from
  the screen contracts (14 needs, 18 routes, agent denials, TRI tags, the footing figures). Not run
  (end pass). The TypeScript fixture assertions ride with T-04-T07's slice. ADR-078's "N's
  session" drops under the solo rules.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3021 | Which fields each artboard needs; the footing figures held | no |
- `2026-11-09` — S32 end pass: gates, unit, contract, S32 integration and web suites run; fixes folded into the end-pass PR. Status done.
