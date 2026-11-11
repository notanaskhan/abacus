---
id: TASK-6810
title: "T-05-T09: E1 TB pipeline tax/compute/entity/tb_pipeline.py: UTB + AJE + RJE = ATB, ATB + TJE = TTB, column footing, balance-sheet and capital ties, statement roll-ups, grouping by form line, unmapped count and export gate; engine_name, engine_version and inputs_hash on every output"
spec: SPEC-651
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: s36-t05-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-05-T09
---

## Objective
Ridgeline ATB total assets 17,914,500 = 11,048,300 + 6,866,200, every column foots to $0, and
Unmapped 1 blocks export in the Run 1 variant.

## Plan (amber: written before the build)
1. `tax/compute/entity/stamp.py` (engine name, version, inputs hash; independent of the
   individual engines), `ties.py` (foot, tie: the compute contract forbids importing the
   workbook's tieouts), `tb_pipeline.py` (`TbAccount`, `run` → `TbResult`: columns, foots,
   balance-sheet tie on ATB and TTB, capital roll-forward tie, section totals, TTB by form line,
   unmapped, export gate with named reasons, stamp).
2. Tests: `tests/unit/tax/test_t05t09_tb_pipeline.py` with TXP-02's 28 Ridgeline accounts.
3. Rollback: revert; nothing calls it yet but T-05's workspace (later rows).

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass); a by-hand run of the pipeline on
  the TXP-02 data gave 17,914,500 assets, 1,256,200 book income and every column at $0.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3408 | Signs, ties, gate reasons, entity stamp and ties modules | no |
