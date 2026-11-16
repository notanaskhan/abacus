---
id: TASK-8363
title: "C-01-T22: Reconciliation engine closes/compute/reconciliation.py (pure, Decimal)"
spec: SPEC-655
acceptance_criteria: [AC-39, AC-40]
risk_zone: amber
status: in-review
branch: c01-t22-reconciliation-engine
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T22
---

## Objective
Spec section: docs/plan/epics/C-01.md §3 F7.
Reconciliation engine closes/compute/reconciliation.py (pure, Decimal).

## Plan (amber)
1. `closes/compute/__init__.py` and `reconciliation.py`: inputs (statement lines, register lines, prior open items), `statement_lines_from_table` over P-11 extracted-table cells with row boxes and the lowest cell confidence, matching (reference, then amount and date window), items, aging, stale rule, carry-forward, difference, tally, `engine_version`, `inputs_hash`, `content_hash`.
2. `backend/pyproject.toml`: `abacus.modules.closes.compute` joins the compute-package import contract.
3. `tests/unit/closes/test_c01t22_reconciliation_engine.py`: the ••4410 fixture from `close_slice` (184,236.18 + 6,412.40 - 5,658.08 = 184,990.50 = 184,610.50 + 380.00; #2281 stale at 193 days), Run 1 off 380.00, hashes stable under reordering, confidence floor, pending without a statement, prior items clearing.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5338). Engine pure (import contract kept); the unit file ran green while building (12 tests). Gates and
  tests run once at the S47 end pass (build first, test last).
