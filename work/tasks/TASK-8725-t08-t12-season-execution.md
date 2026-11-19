---
id: TASK-8725
title: "T-08-T12: Cohort approval and execution rules"
spec: SPEC-710
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t08-t12-season-execution
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T12
---

## Objective
engagements/season_execution.py (pure): human manager-or-above approval only (never agent or system), withdrawal before start only, FIFO per season, and idempotent row steps keyed {season}:{row}:{step} so a re-run creates no duplicate.

## Plan (amber)
1. engagements/season_execution.py; tests/unit/engagements/test_t08t12_season_execution.py.

## Progress log
- `2026-11-19` — Built; tests pass (3). Not built: the approval route with confirm and single-use grant, SeasonSetupExecutionWorkflow and the tax row executor, progress events and retry (they build on these rules and on T-08-T09's persistence). Gates and tests run once at the S51 end pass (build first, test last).
