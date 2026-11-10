---
id: TASK-6617
title: "T-04-T20: Golden fixtures tests/golden/tax_individual from blueprint 9.8 Feld figures, plus hypothesis property tests"
spec: SPEC-649
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s34-t04-t20
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: T-04-T20
---

## Objective
Goldens assert exact Decimal equality for every Feld figure in the screen contracts, property
tests pass 10,000 examples, and an off-by-one rounding mutation is caught.

## Plan (amber)
1. `backend/tests/golden/tax_individual/feld_ty2025.yaml`: the IT-201 inputs and lines, IT-225,
   IT-112-R, Ridgeline's box 2 sourcing and the partner PTET shares, with `source` and
   `reviewed_by` (null until the CPA signs).
2. `test_t04t20_feld_goldens.py`: exact equality per figure; hypothesis (10,000 examples):
   sourcing foots with largest-remainder rounding, allocations conserve, IT-201 idempotent and
   never both due and overpaid; a mutated allocator is caught by the same footing check.

## Progress log
- `2026-11-10` — Written from the blueprint's figures (solo independence). Not run (end pass).
  The IT-201's NY and NYC taxes are engine imports (DEC-77), so the golden feeds 29,791 and 23,014
  as imports; the 6.85% recapture and the NYC brackets are the engine's, not Accrued's.
