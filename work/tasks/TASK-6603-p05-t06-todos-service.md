---
id: TASK-6603
title: "P-05-T06: To-dos service and routes: create, assign, autosave with If-Match, complete, reopen, move, soft delete, checklist up to 8, My to-dos buckets, anchor counts, firm-scope to-dos"
spec: SPEC-650
acceptance_criteria: [AC-14, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30]
risk_zone: amber
status: in-review
branch: s34-p05-t06
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T06
---

## Objective
Marcus's My to-dos returns Overdue 1, Today 1 and This week 2 at the E0 clock, the agent is never
assignee or actor, and every change writes a todo audit event.

## Plan (amber)
1. `collaboration/todos.py` (new): create (engagement or firm scope, optional anchor of the same
   engagement, row text sealed, checklist ≤ 8, `source_thread_id` writes the thread's `converted`
   event), patch under `If-Match`, assign, complete, reopen (= Undo), move within the engagement,
   soft delete (creator, assignee, manager-or-above), checklist add/toggle/remove, seen, reads with
   derived Overdue and bands in the firm's zone, anchor lists and counts.
2. The `todo` anchor provider (`TODO_ANCHORS`), registered in `api.py`.
3. `routes.py`: the to-do routes live (stubs replaced); idempotent create.
4. `repository.py`: to-do reads and writes with `visible()` (firm-scope rows by creator or
   assignee); `update_todo_values`; comment counts per anchor.
5. Matrix (`collaboration.yaml`): `firm_partner` and `firm_manager` allowed on the six `todo.*`
   actions for firm-scope to-dos (decided on the firm resource); `_matrix.py` regenerated.
6. Notifications: `todo.assigned` → `todo_assigned` (registered, `other`, CircleCheck, email on),
   re-checked against the team at fan-out. Reviewed audit actions; `todo` is OPTIONAL_OWNER.
7. Tests: `tests/unit/collaboration/test_p05t06_todos.py` (AC-29 golden bands at E0); the HTTP
   suite is P-05-T07's (its world gains membership levels for AC-28).
Rollback: flag off; revert (no migration).

## Progress log
- `2026-11-10` — Built dark. ruff, pyright clean; the app imports. Tests not run (end pass).
  Partial: My to-dos is one page (`limit`, no cursor; a person's open to-dos are few); HOME-01's
  To-dos band and the C-27 chips read these routes when their screens land (P-05-T10/T13).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3203 | Firm-scope to-dos on the firm resource; delete rule; bands | no |
