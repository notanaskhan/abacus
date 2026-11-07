---
id: TASK-3395
title: A-06-T16 the agent's suggested checklist answers reach their items
spec: SPEC-000  # row (A-06-T16)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T16
branch: s28p-a06-t16-seam
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-06-T28's checklist had no writer for `suggested` answers: A-06-T16's seam ('suggestion targets for ... disclosure answers with appliers') was never built, so the adopt route could never find anything to adopt.

## Plan
- `agents.api.pending_suggestion`: an owner's read of one pending suggestion (no rationale, no citations; hidden runs read as none).
- `reporting.statements`: `record_suggested_answer` mirrors a pending yes or no on an empty or still-suggested item; `apply_suggested_answer` writes adopted or edited in the adopting unit of work, with field history.
- `assurance/checklist_suggestions.py`: the `suggestion.created` subscriber and the `disclosure_checklist` applier (reporting may not import agents, BOUND-002).
- Catalogue `disclosure_checklist.suggested` as a run.
- Rollback: revert; no migration.

## Progress log
- 2026-11-08: built. `tests/unit/assurance/test_a06t16_checklist_suggestions.py` (8), `tests/integration/test_a06t16_checklist_suggestions.py` (1, loads the completion slice on Postgres; found a refused mirror opening a unit of work with no audit event, fixed); unit suites audit_trail, reporting, review, assurance, worker: 1,021 pass, 1 fails on main's own pin (5 S29 subscriptions missing from `test_worker_screening`); lint-imports 7 kept; ruff and pyright clean.

## Decisions made during this task
DEC-2394
