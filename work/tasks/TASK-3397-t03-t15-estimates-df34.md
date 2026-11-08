---
id: TASK-3397
title: T-03-T15 TAX-13 b's estimates, with real confirmation requests and confirmations
spec: SPEC-000  # row (T-03-T15)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: T-03
plan_key: T-03-T15
branch: s28p-t03-t15-estimates
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
DEC-2371 left the estimate confirmations unsent ('no lead to ask'). The handoff's TAX-13 b also disagrees with the seed's seven rows (DF-34: fix seed contradictions in the scenario). Ayush chose to realign all seven.

## Plan
- `tax_schedules.ESTIMATES` as TAX-13 b draws them: Feld Scheduled Sep 15 (Claire Feld, Sep 11), Meera Shah's request sent Sep 8, Calloway Paid Sep 14 (Eleanor Calloway), Varga Paid Sep 9 (Elena Varga), Gloria Mendez Not confirmed, Whitley Not required, Thornbury Prospect; the handoff's inputs (Feld 123,222.73 x 1.1 = 135,545 less 55,585; Shah 148,000; Calloway 46,300 at 110%, 1041-ES, EFTPS; Varga 3,900 and Mendez 6,200 at 100%).
- Loader: each person an active contact (`create_contact`, `activate_contact`) with an engagement contributor grant, the request through `request_estimate_confirmation`, their upload through `evidence.api`, the preparer's acceptance (as `_file_returned` writes a decision), then Q3 scheduled or paid.
- Product fixes the load found (below).
- Also: ANY-001 in #1404's test (stage 1 banned patterns).
- Rollback: revert; no migration.

## Progress log
- 2026-11-08: built. `tests/integration/test_t03t15_load.py` (3 pass on Postgres, the new one reads Q3 and each confirmation's contact and day); `tests/unit/synthetic/test_t03t15_tax_schedules_slice.py` (7). Unit requests, tax, synthetic, assurance and contracts/tax_returns: 1,188 pass, 1 fails on main's own `test_a05t07_ebp_slice` (the ebp slice, untouched here). ruff and pyright clean.

## Decisions made during this task
DEC-2396
