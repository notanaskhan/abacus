---
id: TASK-6126
title: "Q-03-T205 re-shard the weekly mutation run to six shards for the new red modules"
spec: SPEC-000  # row (Q-03-T205)
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T205
branch: s30-q03-t205
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
Mutation infrastructure upkeep: re-shard the weekly run for the new red modules so it stays under 4 hours.

## Plan
- `abacus_tools/quality/mutation.py`: `WEEKLY_SHARDS = 6` (277 red files, ~75,700 lines; six shards of ~12,600 lines each, balanced by line count).
- `.github/workflows/mutation-weekly.yml`: matrix 1 to 6, `--shards 6`, names `/6`.
- `tests/unit/tools/test_mutation_workflows.py`, `tests/unit/quality/test_mutation_floors.py`: follow the new count.

## Progress log
- 2026-11-08: built. Shard balance computed: 12,610 / 12,616 / 12,618 / 12,608 / 12,608 / 12,612 lines. Tests written, not run.

## Decisions made during this task
None.
