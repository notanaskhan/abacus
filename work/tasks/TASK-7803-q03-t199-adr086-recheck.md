---
id: TASK-7803
title: "Q-03-T199: ADR-086 recheck at M15: auto-merge not earned; +15% gain dropped; spill items 1-3 pre-scheduled"
spec: SPEC-000  # row (Q-03-T199; ADR-086; chapter 01 §1.8.7)
acceptance_criteria: [AC-20]  # the row's acceptance, below
risk_zone: amber
status: in-review
branch: lo38-q03-t199-adr086
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
plan_key: Q-03-T199
---

## Objective
"The M15 record states whether auto-merge is earned and the ledger reflects the consequence."

## Delivered
- `docs/ops/gates/M15-season-ready-2028.md`: the autonomy section (not earned; why; consequence).
- `docs/product/capacity-ledger.md`: M15 autonomy recheck (gain dropped; I-04, G-03, X-02 first to
  spill).
- DEC-4801. No code. Rollback: revert the commit.

## Progress log
- 2026-11-12: recorded.
