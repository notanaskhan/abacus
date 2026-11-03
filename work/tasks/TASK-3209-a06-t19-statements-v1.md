---
id: TASK-3209
title: A-06-T19 migration 0660 statements v1, disclosure-checklist templates and the statements stub
spec: SPEC-642
acceptance_criteria: [AC-12]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T19
branch: s26-a06-t19 (stacked on s26-a05-t28)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Up/down/up passes, an override without a reason and an N/A answer without a reason are refused,
and the statements stub returns 501 behind reporting.fs_disclosure."

## Plan (amber)
- Migration 0660 on 0659:
  - DEC-80's tables in `reporting`;
  - the checklist templates in `methodology`;
  - insert-only triggers; human, session-bound approvals;
  - the override and N/A reason CHECKs.
- Flag `reporting.fs_disclosure`. Matrix: the `statement.*` and `disclosure_checklist.*` rows
  (reporting) and `disclosure_checklist_template.import/publish` (methodology).
- `reporting/statements_contract.py`: the §4.3 routes as 501 stubs.
- Registries and `IMMUTABLE_TABLES`; `completion.md` §Statements v1.
- Fixed duplicate operation ids: `tax_estimates_route` (from T-03-T02), `fs_statements_route`
  and `fs_send_draft_route`.
- Test: `tests/integration/test_a06t19_statements_migration.py`.
- Rollback: `alembic downgrade 0659`.

## Progress log
- 2026-11-03: built. Lesson: run the OpenAPI export with `-W always` after adding routes, because
  FastAPI only warns on duplicate operation ids. Tests at the S26 end review.

## Decisions made during this task
DEC-2209.
