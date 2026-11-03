---
id: TASK-3040
title: Q-04-T087 M14 ops retro part AY, rehearsed on the synthetic test firm
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # the retro numbers reproduce from snapshots and logs and are in the capacity ledger before re-baseline #4
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T087
branch: s25-q04-t087
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"The retro numbers reproduce from snapshots and logs and are in the capacity ledger before
re-baseline #4." Run on PF-X1 and reported as synthetic (DEC-1530, DEC-2081).

## Plan (amber)
- `abacus_tools/m12_pack.py`: with `--code`, each firm's rows carry its pilot code, never its name
  (the pack is committed; firm names never enter git).
- `docs/ops/pilot/retros/m14-ops-retro-ay.md`: the retro and the pack for S22-S25.
- `docs/product/capacity-ledger.md`: the M14 ops retro section.
- Tests: `test_t087_a_committed_pack_names_each_firm_by_its_pilot_code` (unit) and the integration
  test's "no firm name" check.
- Rollback: revert. No migration, no flag.

## Result
Every firm figure is zero or no data on the synthetic firm; support hours 0 against the reserve,
RK-07 not fired, no flips. W1, W3, W9 and W10 are F-09's (F-09-T186).

## Progress log
- 2026-11-03: built. Pack unit 11 passed; integration 1 passed.

## Decisions made during this task
DEC-2081 (TASK-3034).
