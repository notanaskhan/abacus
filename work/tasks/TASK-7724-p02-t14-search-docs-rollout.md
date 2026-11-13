---
id: TASK-7724
title: P-02-T14 C15 docs, runbook, skills, inventory and flag rollout
plan_key: P-02-T14
spec: SPEC-000  # docs/contracts/c15-search.md; ADR-241
acceptance_criteria: [AC-1]  # the guide lets C-01 and W-02 register with no platform change; flags dated
risk_zone: green
status: in-review
branch: p02-t14-search-docs
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
C15 v1 freeze note and registration guide, platform README, the drift/rebuild runbook and the
RB-13 offboarding step, `backend-module` and `frontend-feature` skill updates, the data inventory
row, the per-firm flag rollout and retirement plan.

## Plan
- `docs/contracts/c15-search.md` §5–§6; `backend/src/abacus/modules/platform/README.md`.
- `docs/runbooks/RB-82-search-index-drift.md` (new), `RB-13` module step, runbook index row.
- `.claude/skills/backend-module/SKILL.md`, `.claude/skills/frontend-feature/SKILL.md`.
- `docs/architecture/data-model.md` rows; `docs/operations/p02-search-flag-plan.md` (new).
- `brightwater_hale/loader.py` `FLAGS_ON` + `search.palette`; `docs/screens/SHL-02.md` status.
- `infra/envs/staging/search.tf`, `indexer.py`, `loadtest/search.py`: runbook RB-82.
- Rollback: revert.

## Partial
- "Flags on for staging and the canary": on with the next scenario load of the synthetic firms
  (this PR); the staging load itself runs at the S41 batch deploy (human).
- No real firm is live (DEC-1391): every real-firm flip in the plan is planned, not scheduled.

## Progress log
- 2026-11-13: written; validate_docs and tests not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4727 | freeze and guide; RB-82 not RB-31; synthetic-firm flag; dated retirement | no |
