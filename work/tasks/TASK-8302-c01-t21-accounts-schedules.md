---
id: TASK-8302
title: "C-01-T21: Accounts and schedules service"
spec: SPEC-655
acceptance_criteria: [AC-35, AC-36, AC-37, AC-38]
risk_zone: amber
status: in-review
branch: c01-t21-accounts-schedules
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T21
---

## Objective
Spec section: docs/plan/epics/C-01.md §3 F6.
Accounts and schedules service.

## Plan (amber)
1. `closes/compute/schedules.py` (pure): straight-line amortisation, depreciation and accrual build-up per period (last period takes the rounding), the tie (`tie`, `off`, `ties_once_posted`, `recorded`), rollups, inputs hash.
2. `closes/accounts.py`: the CLS-04 tree (classification, type, account; reconciliation and schedule words), the register, arrangements and their versions (person only, `If-Match`), the workpaper with kept results and a `schedule` exception when off, workpaper.xlsx, recategorisation as a C8 reclass proposal, the `close_entry_recordings` matcher.
3. `evidence/render.py` (protected): `render_close_workpaper` (strings never formulas).
4. `ledger/cas_reads.py` (red, additive): `CitedRegisterRow` gains the row's category and the snapshot's period.
5. Routes in `closes/contract_work.py` call the service; audit kinds reviewed; `arrangement` audit owner.
6. Tests: `tests/unit/closes/test_c01t21_schedules.py`, `tests/integration/test_c01t21_accounts_schedules.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5302). Lint and pyright clean; the unit file ran green while building (7 tests). Gates and
  tests run once at the S47 end pass (build first, test last).
