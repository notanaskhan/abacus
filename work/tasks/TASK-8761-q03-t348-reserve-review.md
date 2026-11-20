---
id: TASK-8761
title: "Q-03-T348: Quarterly reserve review 2028 Q3: burn by workstream against this plan, escaped-defect retro (the layer that should have caught each defect), lane reallocation and calibration inputs"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s51-q03t348
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-03-T348
---

## Objective
The review is recorded in the capacity ledger and the next quarter's lanes are re-sized.

## Plan (green)
1. Burn by workstream for S45–S51 against the plan's sizes.
2. Escaped-defect retro from this round's findings, each with the layer that should have caught it.
3. Lane reallocation and calibration inputs.
4. Record in `docs/plan/status/Q-03-reserve-review-2028Q3.md`.
5. Rollback: revert the PR (docs only).

## Progress log
- `2026-11-20` — Written from the S51 build logs and this round's findings. Per-row hours are not kept, so burn is by the plan's sizes; the next quarter's lane sizes are proposals for the builder to adopt. Gates and tests run once at the S51 end pass (build first, test last).
