---
id: TASK-8719
title: "T-06-T24: E10 S-corporation engine: AAA, PTI, E&P, OAA and per-share per-day allocation"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t24-s-corp
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-06-T24
---

## Objective
tax/compute/s_corp.py (pure Decimal): AAA roll (distributions never take AAA below zero; losses can), §1368(c) distribution ordering (AAA, PTI, E&P, OAA, then basis), and per-share per-day allocation to whole dollars by largest remainder. Bluestem's 1,488,200 splits 70/30 as 1,041,740 / 446,460.

## Plan (amber)
1. tax/compute/s_corp.py; tests/unit/tax/test_t06t24_s_corp.py.

## Progress log
- `2026-11-19` — Built; tests pass (3). The TXP-13 service and routes are T-06-T42 (S53). Gates and tests run once at the S51 end pass (build first, test last).
