---
id: TASK-8602
title: "T-08-T03: Protected bundle: matrix, flags, status rows, glossary, error codes, kinds, C13 events"
spec: SPEC-710
acceptance_criteria: [AC-31, AC-34]
risk_zone: red
status: in-review
branch: t08-t03-protected-bundle
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: T-08-T03
---

## Objective
Spec section: docs/plan/epics/T-08.md §4.4, §4.8, §4.9, §4.10. One protected bundle: matrix actions for seasons, deadlines, two-year, standards runs, planning, amendments and AARs with agent denials; six flags; status rows; glossary rows; error codes; notification kinds; C13 events. TABLE_OWNERS land with each migration (T05–T07).

## Plan (red)
1. Matrix rows in permission-matrix/engagements.yaml (3), practice.yaml (2), tax.yaml (14); the agent is deny on every write, task_scope on reads with use + ai_disclosure where TRI; filing_deadline.apply_postponement needs fresh MFA (group standards).
2. Six flags default off: engagements.season_setup, practice.filing_deadlines, tax.two_year, tax.standards_runs, tax.planning, tax.amendments (expires 2027-05-17, inside the 180-day override; not in a busy-season window).
3. Status objects season_cohort, season_manifest_row, standards_run, standards_run_item, check_result, variance_explanation, planning_opportunity, amendment; glossary section with 13 terms (DEC-14: filing_deadline, never a bare deadline).
4. Error modules engagements/season_errors.py and tax/practice_tools_errors.py imported from api.py; error-codes.yaml rebuilt.
5. Eight notification kinds with catalogue events and templates; four C13 events in review/gates.py.
6. Regenerated: _matrix.py, _flags.py, _statuses.py, status.gen.ts, actions.gen.ts, generated security tests. Rollback: revert the PR (no data).

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5602). The human-only register is not extended: the T-08 tables carry human-only CHECKs bound to the actor GUCs instead (T05–T07), so no register migration is needed. Gates and tests run once at the S50 end pass (build first, test last).
