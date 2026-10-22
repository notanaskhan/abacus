---
id: TASK-410
title: Migration 0095 - agent suggestions and proposals with the 10-second Undo trigger (P-04-T05)
spec: SPEC-308
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T05
branch: p04-t05-suggestions-proposals
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"An undone row more than 10 seconds after its decision or after a consumed grant is refused by trigger, and every decision table is insert-only and human-only."

## Plan
- Migration 0095, owned by `agents`, with its registry.
- The schema_check immutable list and its expectations.
- A `Seeder.as_actor` test helper.
- The integration test.
- Rollback: `alembic downgrade 0094`.

## What changed
- **`suggestions`:** the app may update only status and version.
- **`suggestion_decisions`:** insert-only and human-only.
  - An Undo names its decision.
  - An edit carries a value.
- **`proposals`:** the app may update only state, `routed_to_user_id` and version.
- **`proposal_rows`:** insert-only.
- **`proposal_decisions`:** insert-only and human-only.
  - A rejection needs a reason code.
  - Routing names a person.
  - The row carries `approval_grant_id`.
- **The `*_undo_window` triggers refuse an Undo (`undo_window_closed`) when:**
  - the original is more than 10 seconds old in business time (`abacus_now()`, the clock that stamped it);
  - it is on another subject;
  - it is itself an Undo;
  - or it was already undone.
- **Grant check:** "after a consumed grant" needs `approval_grants` (P-04-T10). Its trigger condition lands with that table. Until then no decision carries a grant.

## Progress log
- 2026-10-22: `tests/integration/test_proposal_undo_window.py` passes:
  - Undo at +7 s, then a second Undo refused;
  - Undo at +11 s refused;
  - an agent decision refused;
  - UPDATE and DELETE refused even for the owner.
- 2026-10-22: `test_schema_check_db` passes (180).
- 2026-10-22: the CHECK sets match the P-04-T02 status vocabulary.
