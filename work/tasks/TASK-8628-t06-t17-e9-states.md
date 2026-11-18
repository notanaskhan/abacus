---
id: TASK-8628
title: "T-06-T17: E9 apportionment and PTET engine"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t17-e9-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-06-T17
---

## Objective
Spec section: docs/plan/epics/T-06.md §3 F4 (TXP-09). Per-property sourcing, shares summing to 100.0, PTET = base x rate, partner credits by period-weighted percent through allocate with a recorded per-partner half-up override, payment-gap and unmapped-factor detection; state rate files.

## Plan (amber)
1. tax/compute/states.py: rates/rate (ParameterMissing when unpublished), apportion (numerators must foot), ptet (half up), partner_credits (half-up partners fixed, the rest by largest remainder; foots exactly), payment_gaps.
2. tax/compute/parameters/ptet/ty2025.yaml: IL 4.95, CO 4.40, NY 6.85 (reviewed_by null until the CPA memo).
3. tests/unit/tax/test_t06t17_states.py: 46.0/31.5/22.5; 28,044 + 17,070 + 18,982 = 64,096; every credit cell of the TXP-09 table; Feld 16,025.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5628). Partial: only the TY2025 rate file ships; TY2026-TY2028 rates are CPA-published reference data and are not invented (the engine refuses an unpublished year). Gates and tests run once at the S50 end pass (build first, test last).
