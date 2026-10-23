---
id: TASK-967
title: Request lifecycle v2 — edit, delete, send with scope and model-text checks and Undo, waive, Ignore and return, delegate, incorporate, activity, upload intents and the live poll (P-06-T10)
spec: SPEC-319
acceptance_criteria: [AC-11, AC-12, AC-13, AC-14]
risk_zone: amber
status: done
epic: P-06
plan_key: P-06-T10
branch: s5-request-lifecycle
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"A delegated third party sees exactly one request, an out-of-scope client wording answers 409 and sends nothing, and an unchanged model-drafted wording answers 409 model_text_not_permitted while the firm's P-25 setting is off."

## Plan (amber)
- **Migration:** `0113_request_wording_edit.py` grants `UPDATE (description)` on `request_items`. Rollback: `alembic downgrade 0112`.
- **Code:**
  - `requests/lifecycle.py` (new);
  - routes in `requests/contract.py`;
  - repository writes;
  - the `RequestItemSent` event;
  - seams: `comments.scope_check()`, `binders.activity_view`, `engagements.api.contact_portal_user`, `identity.grant_client_access(action="request_item.delegate")`, the `request_item` scope resolver, and `requests.api.register_live_facts`.
- **Tests:** `tests/integration/test_request_lifecycle.py` (9); `test_c5_stub.py` `IMPLEMENTED` gains the 12 routes.

## Progress log
- 2026-10-23: built. One gap, recorded in DEC-158: the delegate's read of their one request needs matrix cells for the `delegate` grant role (P-09), so AC-13's "sees exactly one request" holds as a grant on exactly one request but reads nothing yet. The live poll's inbox and screening facts read 0 and false until an owner registers them.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-158 | send as a one-request publish; delegate grant; deferred read cells | no |
