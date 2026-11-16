---
id: TASK-8315
title: "A-09-T19: Consolidation compute engine ledger/compute/consolidation.py (pure)"
spec: SPEC-658
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
branch: a09-t19-consolidation-engine
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T19
---

## Objective
Spec section: docs/specs/SPEC-658 F3.
Consolidation compute engine ledger/compute/consolidation.py (pure).

## Plan (red)
1. `ledger/compute/consolidation.py` (pure, Decimal; the compute import contract): level columns from mapped entity TBs, posted eliminations by level (level 1 carries every one), consolidated = entities + the eliminations' net debit, per-entity attribution of assets, ties (every column nets to zero), total assets and net income, inputs hash.
2. `ledger/consolidation_xlsx.py`: one sheet per level through `kernel.safe_xlsx` (fixed clock, no formulas): byte-identical renders.
3. Tests: `tests/unit/ledger/test_a09t19_consolidation_engine.py` on the Harlow & Pike seed figures. Rollback: revert (nothing reads the engine yet).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5311). The unit file ran green (6 tests: Level 1 total assets 50,760,000 with every column netting to zero; Level 2 39,760,000 with net income 4,760,000; byte-identical renders). Partial: the TB read route, lock and reopen with reason, export, `register_reviewable` and `register_export_section` still answer 501 / are not registered: they need the entity TB mapping read (AUD-31's mapped lines) joined to the engine. Gates and
  tests run once at the S47 end pass (build first, test last).
