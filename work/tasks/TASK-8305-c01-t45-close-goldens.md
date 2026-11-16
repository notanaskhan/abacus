---
id: TASK-8305
title: "C-01-T45: Golden fixtures and Hypothesis properties for the reconciliation engine, schedules and rollups"
spec: docs/plan/epics/C-01.md §6
acceptance_criteria: [C-01-T45]
risk_zone: amber
status: in-review
branch: c01-t45-close-goldens
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: C-01-T45
---

## Objective
Golden fixtures and Hypothesis properties for the reconciliation engine, schedules and rollups.

## Plan (amber)
1. `tests/golden/closes/closes_figures.yaml`: the ••4410 reconciliation both sides, aging buckets and stale #2281, prepaid 8,400 / 12 = 700 and 2,800 at August, flux both-legs results, tree footing (quoted Decimal text).
2. `tests/golden/closes/test_c01t45_goldens_properties.py`: exact-Decimal goldens and Hypothesis properties over 500 generated ledgers (a consistent month ties, carry-forward conserved, pairings one-to-one, hashes order-independent, schedules foot, rollups foot).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Goldens and properties ran green while building (11 tests, 500 examples each). Gates and
  tests run once at the S47 end pass (build first, test last).
