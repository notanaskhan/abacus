---
id: TASK-1205
title: Client ignore note and undo — ignore/undo and mark-done/undo as compensating events (R-01-T08)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: amber
status: done
epic: R-01
plan_key: R-01-T08
branch: s8a-portal-pbc
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Undo returns Claire's ignored 1099-B to To do and Kevin's BND-02 row to Requested, while undo
after Kevin waived the request answers 409."

## Plan (amber zone)
- **Migration 0157** (`down_revision` "0146"): `comments.origin text NOT NULL DEFAULT 'thread'
  CHECK (origin IN ('thread', 'ignore_note'))`; the app's insert grant gains `origin`. Rollback:
  `alembic downgrade 0146` (restores the grant, drops the column; ignore notes stay as plain
  shared comments).
- **The note:** `lifecycle.ignore_item` stores the optional note as a sealed, shared client comment
  with origin `ignore_note` in the Ignore's unit of work (audit `request_item.ignore_note_added`,
  ids only), and no longer copies it into `client_item_responses.note`.
- **The undos** (`requests/client_undo.py`, new; the "transition table" is its `COMPENSATIONS`:
  each compensating event, the act it undoes and the firm acts that close it):
  - `POST /v1/portal/request-items/{id}/ignore/undo`: clears `client_ignored_at`, appends a
    `withdrawn` SPEC-042 response, audit and outbox `request_item.ignore_undone`.
  - `POST /v1/portal/binders/{id}/mark-done/undo`: Complete back to Published, the mark-done stamps
    cleared, audit and outbox `binder.mark_done_undone`.
  - Allowed until the firm acts (R-01 OQ-2, DEC-240), by the person who acted; 409
    `firm_already_acted` once the firm waived, returned or received the request (or, for the
    binder, sent, waived or returned a request in it since); a second Undo is 409; another person
    is 403. Idempotency-Key: authorised before the replay lookup (ED-023's shape).
- **Undo contract suite:** both cases registered in `tests/contracts/undo/test_undo_contract.py`
  with a window kind `until_firm_acts` (DEC-334): the shared checks (compensating row by the same
  person, the decision's rows kept, a second Undo refused, another person refused) run for them;
  the 10-second checks stay for the 10-second cases; a new check proves the client window outlives
  10 seconds and closes with 409 `firm_already_acted` when the firm acts.
- **Registry edits:** `requests/registry.py` comments insert columns; events in `requests/events.py`.
- **Deferred:** in-app kinds for the undos: nothing consumes `binder.marked_done` in-app yet
  (no notification kind exists to retract); recorded in DEC-334.
- **Tests:** `tests/integration/test_portal_undo.py` (the AC, the note as a shared comment, the
  409s, scope 404); the undo suite cases.

## Progress log
- 2026-10-25: plan written.
- 2026-10-25: built as planned. Migration 0157 (`down_revision` 0146). The note lands as a shared
  `ignore_note` comment in the Ignore's unit of work; `client_item_responses.note` is no longer
  written by the Ignore. `requests/client_undo.py` holds `COMPENSATIONS`, `FirmAlreadyActed` and
  `NothingToUndo`; `lifecycle.undo_ignore`/`check_ignore` and `binders.undo_mark_done`/
  `firm_acted_since`. `request_item.ignore` requires a reason in the matrix, so the Undo passes
  the code `undo`. Undo suite: two cases, window `until_firm_acts`, the 10-second check limited
  to the 10-second cases, two new checks (outlives 10 s; 409 after the firm acts): 29 pass.
  `tests/integration/test_portal_undo.py` (6). DEC-334. Deferred: in-app kinds (none exists for
  `binder.marked_done` to retract).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-334 | The client undo window is "until the firm acts", not ADR-161's 10 seconds | No (R-01 R8, OQ-2; DEC-240) |
