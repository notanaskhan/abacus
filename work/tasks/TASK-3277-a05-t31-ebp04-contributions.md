---
id: TASK-3277
title: A-05-T31 EBP-04 contributions and remittance timeliness screen
spec: SPEC-000  # row (SPEC-640 F6)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T31
branch: s27-a05-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s27
created: 2026-11-04
updated: 2026-11-04
---

## Objective
"Every amount foots on screen, the Dec 26 row shows 9 business days, and state f reads 'Corrected
Sep 30' only after a person records the correction."

## Built
- Backend: `GET /v1/audits/{wi}/ebp/contributions/payrolls` (`list[PayrollOut]`: pay date, deposit,
  lags, deferrals and total by code, late) over `ebp_payrolls` through `ebp_remittances.payrolls`;
  contract test `tests/contracts/a05_ebp/test_a05t31_payrolls.py`; client regenerated.
- `apps/web/src/screens/EBP-04/` (`Contributions.tsx`, `copy.ts`, `index.tsx`, `scenarios.ts`,
  test): the cockpit canvas for `?section=ebp_04`: segmented Reconciliation · Timeliness · Testing,
  tally strip (the server's `tie.*` rows, late count, lost earnings, receivable), Card A (ledger
  rows with the AJE-1 status pill), Card B (26-dot timeline, practice caption, the late payroll),
  Card C (both day counts, lost earnings, recorded correction status, Form 5330, the 4a preview),
  Raise exception… and Draft 4a schedule; Timeliness lists every payroll; d from the rail's running
  state. AUD-02 renders it.
- Fixtures: `fixtures/seed/ebp04.ts`, `fixtures/scenarios/EBP-04.ts` (a, b, d, e, f, off).

## Progress log
- 2026-11-04: built; tsc and eslint clean. Tests written, run at the end pass.

## Decisions made during this task
DEC-2257.
