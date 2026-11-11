---
id: TASK-7305
title: "T-05-T14: E5 part 2, targeted waterfall with hypothetical liquidation at book value (return of capital, preferred return on unreturned LP capital, GP catch-up, promote and residual) and the back-solve plug; preview mode; every check foots exactly"
spec: SPEC-651
acceptance_criteria: [AC-5]  # the spec's section ids (validate_docs reads AC-<n>)
risk_zone: amber
status: in-review
branch: s37-t05-t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: T-05-T14
---

## Objective
Harborview distributes 4,000,000 + 312,000 + 78,000 + 510,000 = 4,900,000, plugs 900,000 and
gives the GP 20%.

## Plan (amber)
- `backend/src/abacus/modules/tax/compute/entity/waterfall.py` (PROTECTED compute package, pure):
  `run_waterfall(partners, rungs, income)` → rung results, targets, plugs, the GP's profit share,
  checks and the engine stamp. Rules: `return_of_capital`, `preferred_return` (rate on unreturned
  LP capital, day fraction), `catch_up` (target and share), `promote` (gp percent), `residual` and
  `straight_pct` (split or by capital). Whole dollars; every split through
  `kernel.numeric.allocate`.
- Test: `backend/tests/golden/tax_entity/test_t05t14_waterfall.py` against T-05-T11's
  `harborview_waterfall` goldens, the preview's purity and stamp, a short distributable and the
  refusal codes.
- No migration (0821's `allocation_rungs.params` hold the rung parameters), no route: TXP-06's
  preview and save routes are T-05's API rows (T-05-T21 onward) and call this engine.
- Rollback: revert.

## Progress log
- `2026-11-12` — Built (S37). A one-off run reproduced every Harborview golden
  (4,000,000 / 312,000 / 78,000 / 510,000; targets 280,000 / 2,843,077 / 1,776,923; plugs
  180,000 / 443,077 / 276,923; GP 20.00%). The golden tests are written, run at the end pass.
