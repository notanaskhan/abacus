---
id: TASK-8513
title: "T-06-T13: E3 depreciation engine in tax/compute with TY2025-TY2028 parameters"
spec: SPEC-702
acceptance_criteria: [AC-1, AC-2, AC-4, AC-6]
risk_zone: amber
status: in-review
branch: t06-t13-e3-depreciation
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: T-06-T13
---

## Objective
Spec section: docs/plan/epics/T-06.md §3 F1. E3 (pure, Decimal): MACRS GDS, SL/150DB/200DB, MM/HY/MQ with the mid-quarter test, bonus by acquisition or binding-contract date, §179, the §163(j) small-business test, crossfoot, ties to TB 1600/1650/5600 and Form 8825 by property, recapture classes; parameter files ty2025 to ty2028.

## Plan (amber)
1. `backend/src/abacus/modules/tax/compute/depreciation.py`: formula MACRS (equal to Rev. Proc. 87-57 tables up to their rounding), DB with the SL switch, conventions and the §168(d)(3) 40% test, bonus_rate/bonus_check (no cited date: check, INV-2), year_row, largest-remainder rounding, register with by-property totals and crossfoot, ties, section_179_allowed, small_business_exempt, recapture_class.
2. `compute/parameters/depreciation/ty2025..ty2028.yaml` (protected; reviewed_by null until the CPA memo): bonus cut-off Jan 19, 2025 at 100%, phase-down 40/20/0; §179 and §163(j) for 2025 and 2026; 2027 and 2028 null (not yet published), which the engine refuses (ParameterMissing).
3. Tests `tests/unit/tax/test_t06t13_depreciation.py`: Ridgeline 2025 gives 733,500 and 2,625,167 = 1,891,667 + 733,500 with the handoff's rows, Form 8825 169,500/360,000/204,000, the bonus check, 87-57's 5- and 15-year rows, MQ, §179, §163(j), and a hypothesis crossfoot property; 100% line and branch.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5513). 10 tests pass, 100% line and branch (run once: a pure engine). The property test found a Decimal residue dividing by a spent recovery period; the last part-year now takes the rest. Gates and tests run once at the S49 end pass (build first, test last).
