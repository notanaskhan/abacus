---
id: TASK-7901
title: T-05-T50 Fix flow on the entity workbook
plan_key: T-05-T50
spec: SPEC-651
acceptance_criteria: [AC-F8]  # approving the M-2 fix starts Run 3; the issue resolves when the tie passes
risk_zone: amber
status: in-review
branch: t05-t50-workbook-fix
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
A tie-out issue's fix instructions become a proposed set of workbook cell changes; approving it
writes the cells as the approver's, checkpoints, and re-runs the owning groups; the issue resolves
as the system when the tie passes.

## Plan (amber)
- Files: `tax/workbook_fix.py` (new: grammar, `fix`, adapter `apply_fix`, registration),
  `tax/fix_runner.py` (`_entity_fix` branch in the activity), `tax/api.py` (register),
  `review/issue_runs.py` (no resolve on approval for `system_resolved_only`),
  `audit_trail/activity_reviewed.py` (`workbook.fix_applied`), contract note.
- No migration, no new route (SHL-15's fix instructions and SHL-10's decision are P-04's).
- Tests: `backend/tests/unit/tax/test_t05t50_workbook_fix.py`.
- Rollback: revert the PR (an applied fix's values stay as the approver's versions).

## Partial
- ~~No model step~~: free text goes to `issues.fix_runner.workbook@v1`, checked by code (TASK-7932, DEC-4927).
- Rows carry no citations (the person's instruction is the source); the TXP-11 "Proposed" ghost
  values read the proposal's rows (T-05-T58/T59 screens).
- The issue's "In progress → Resolved" timeline and the Issues badge (11 → 10) are TXP-10's read
  (T-05-T51) over review's own state.

## Progress log
- 2026-11-13: built; tests written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4901 | code parses the fix; proposal kind, adapter and group re-run | no |
| DEC-4902 | self-check issues resolve only when the check passes | no |
