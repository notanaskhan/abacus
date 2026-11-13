---
id: TASK-7721
title: I-02-T12 Today scenarios and seed footing tests
plan_key: I-02-T12
spec: SPEC-654
acceptance_criteria: [AC-1.1, AC-1.3]
risk_zone: green
status: in-review
branch: i02-t12-today-scenarios
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
SHL-23 full and 1 to 7 and HOME-05 a to f as fixture scenarios (Daniel Reyes, Margaret Okonkwo,
Felix Andersen for the quiet day; Mon Sep 14 9:24 and 9:26 AM CDT, Tue Dec 1 8:30 AM CST), the
FakeModel briefing output, Late-provider and layout overrides, and the footing tests 11 = 3 + 6 + 2,
9 = 1 + 6 + 2, 4 = 6 - 2 and 4 = 2 + 2.

## Plan
- `apps/web/src/fixtures/scenarios/SHL-23.ts`, `HOME-05.ts` (new), `fixtures/today.foot.test.ts`.
- `backend/src/abacus/modules/agents/briefing/today.py` (`fake_briefing`),
  `agents/fake_responses.py` (registered), test
  `backend/tests/unit/briefing/test_i02t12_fake_briefing.py`.
- Rollback: revert; nothing in production reads fixtures or the fake.

## Partial
- "Every artboard renders in /components/screens": the gallery registers built components only;
  the SHL-23 panel (I-02-T15) and HOME-05 (I-02-T16) register and read these scenarios.
- SHL-23 "composed" (DF-04, walls, History) is recorded in the contract, not a scenario here.

## Progress log
- 2026-11-13: built; eslint, tsc, ruff, pyright clean; tests written, not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4724 | scenarios now, gallery with the screens; Felix's quiet day; the fake briefing | no |
