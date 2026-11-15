---
id: TASK-8031
title: "C-01-T13: Copperleaf CAS figure book and typed FE fixtures"
spec: SPEC-655
acceptance_criteria: [AC-2, AC-3, AC-7, AC-28, AC-39, AC-49]
risk_zone: green
status: in-review
branch: c01-t13-figure-book
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T13
---

## Objective
The Copperleaf CAS figure book (C-01 §5.3 "seed facts that must foot") with footing assertions,
the synthetic close slice the seed loads, and typed FE fixtures the CLS screens read.

## Plan
1. [x] Figure book `backend/tests/golden/scenario/brightwater_hale/copperleaf_close_figures.json`,
   transcribed from C-01 §5.3 and CLS-01, CLS-02, CLS-05, CLS-06, CLS-09, CLS-10, POR-11.
2. [x] Slice `abacus_tools/synthetic/scenarios/brightwater_hale/close_slice.py`: the 22-close
   portfolio, Run 1 and Run 2 task groups, the seven issues and four notes, the account tree, the
   ••4410 reconciliation with statement page 2, Square, the prepaid schedule, the 13 flux lines
   and drivers, plan v3 (23 rows, 8 request templates), POR-11's 9 requests and 3 questions,
   KNW-04 a. No database code: T14/T15 services load it.
3. [x] Golden test `tests/golden/scenario/test_c01t13_close_figures.py` (25 footing tests).
4. [x] FE `fixtures/seed/close-book.ts` typed against the C-01-T04/T05 contracts (CloseListOut,
   CloseRunOut, CloseRunsOut, RunningClosesOut, CloseReconciliationOut, CloseIssuesOut,
   FluxSetOut, PlanVersionOut, PortalQuestionsOut); `handlers/closes.ts` serves them (the
   portfolio filters by status, past due, attest and search); `fixtures/contracts/
   close-figures.test.ts` foots them against the same book.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010).
- `2026-11-15` — Built. Every §5.3 fact foots: 22 = 3 + 11 + 5 + 3; 51 open; Copperleaf 9 / 21 =
  43%; Run 2 = 2 + 3 + 2 + 1 + 1 = 9 (6 done, 3 at once, 4 open items), Run 1 = 22; 7 = 2 Medium +
  5 Low, 4 notes; tree 539,055.45 = 163,543.05 + 375,512.40; ••4410 184,236.18 + 6,412.40 −
  5,658.08 = 184,990.50 = 184,610.50 + 380.00, #2281 at 193 days; Square 73,166.90 − 1,684.54 =
  71,482.36 over 21; prepaid 8,400 / 12 = 700, 3,500 vs 2,800; flux 13 tested, Payroll +7,670
  (12.5%) = 4,350 + 1,850 + 1,470, Repairs +2,560 (400.0%), Marketing (38.4%) and COGS 4.5% within,
  net income 31,455 → 27,795; plan v3 23 = 8 + 15, 8 requests (7 in v4); POR-11 9 = 7 + 2 and 3
  questions; KNW-04 a 20,020 within, 14,900 held. Not run (end pass).
- **Decision.** Three CLS-01 percentage cells disagree with their own counts; code's figure wins
  (DEC-5054).
- **Partial.** CLS-03 (intake tree, questionnaire), CLS-04 (account tree rows, register,
  workpaper) and the decision-card and failed-task variants of CLS-02 get their fixture rows with
  their screen rows (T18–T20, T21, T33+); the figures they need are already in the book. The
  slice loads through the services (T14, T15; T44 seed tests).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5054 | Reconciled percentage is computed half up; three artboard cells are design slips | no |
