---
id: TASK-6704
title: "P-05-T09: todo_assigned and mention.created notifications, workpaper anchor for AUD-09 rows and cells, convert to review note through C3"
spec: SPEC-650
acceptance_criteria: [AC-1, AC-7, AC-15]
risk_zone: amber
status: in-review
branch: s35-p05-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T09
---

## Objective
Hannah gets one in-app and one email mention with no comment text, Exceptions!A3 opens a thread, and Convert to review note raises an open AUD-17 note in the same unit of work.

## Plan (amber)
1. Notifications: `mention.created` (second source of P-01's `mention`) and `todo_assigned` were
   registered with P-05-T05/T06 (S34) in `notifications/catalogue.py`; nothing registers twice.
   Email goes through P-01's generic path (`communications.notification_email`, template key
   `notification.<kind>`): no code, the templates are DB content (human to-do below).
2. `workpapers/anchors.py` (new): `workpaper` anchor provider, locator `{sheet, cell}` /
   `{sheet, row}` / `{sheet}`, label composed at read time, internal (never shareable); registered
   from `workpapers/api.py` through `collaboration.api.register_anchor` (edge already allowed).
3. `review/notes.py`: `_write_raise` split so `_write_raise_in(tx, …)` writes in a caller's unit of
   work; `raise_on_target_in` exported as `review.api.raise_review_note_in`.
4. `collaboration/threads.py`: `convert_to_review_note` (first live firm comment as the body, the
   anchor as the reviewable, the locator as the note's `cell`/`region` pin, `converted` event and
   `comment_thread.converted` in the same unit of work); a shared thread answers 409
   `thread_shared` (new error code). Route implemented (501 stays declared).
5. Tests: `tests/unit/collaboration/test_p05t09_anchor_places.py`,
   `tests/integration/backfill/test_p05t09_workpaper_anchor.py`.
6. Rollback: revert; `collaboration.v2` stays off.

## Human to-do
- Import `notification.todo_assigned` (and check `notification.mention`) per environment through the
  C16 platform import before `collaboration.v2` flips (see the email-template rule in memory).

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
