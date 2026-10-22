---
id: TASK-418
title: Idempotency-Key kernel and held delivery (not_before, grant-held effects) [mig 0099] (P-06-T06)
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T06
branch: p06-t06-idempotency
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"A retried publish returns the stored response and dispatches no second email."

## Plan
- Migration 0099.
- `kernel/uow/idempotency.py`.
- `UnitOfWork.emit(not_before=, grant_id=)`.
- The relay's held delivery and grant-consumer slot.
- schema_check owners and insert columns.
- The integration test.
- Rollback: `alembic downgrade 0097`, then revert.

## What changed
- **`idempotency_keys`:** one row per (tenant, actor, route, key), insert and read only. It stores the first response and the request hash.
- **`idempotent(ctx, route=, key=, body=, run=)`:**
  - a retry within 24 h with the same request replays the stored response and doesn't run the effect;
  - the same key with another request answers 422 `idempotency_key_reused`;
  - a malformed key answers 422 `idempotency_key_invalid`;
  - two concurrent first requests keep the first stored answer.
- **`outbox.not_before`:** the relay doesn't claim an event before this time. A send can wait out an Undo window.
- **`outbox.grant_id`:** at delivery the relay calls the grant consumer, which identity registers as `consume_grant` (P-04-T10). The event is published only if the grant is consumed. A voided grant (an Undo) delivers nothing and is logged `outbox.grant_void`. With no consumer registered, a held event waits and retries with backoff, so nothing goes out.
- **Not done:** routes adopt the key as they ship. Binder publish adopts it in the C5 implementation.

## Progress log
- 2026-10-22: the new `tests/integration/test_idempotency.py` covers:
  - the retry replays the response with one dispatch, and a different request is refused;
  - a `not_before` event waits, a granted event is delivered, and a voided one is not.
