# Reference: unit of work, audit events, outbox

The pattern every module copies (SPEC-000 §22). Binding rules: ADR-004, ADR-007, ADR-018, ADR-031. Code: `backend/src/abacus/kernel/uow/__init__.py` and `relay.py`; kernel rules in `backend/src/abacus/kernel/README.md`. Layering is in [backend-module.md](backend-module.md); authorisation in [tenancy-and-authz.md](tenancy-and-authz.md).

## A state change

```python
# modules/requests/service.py
async with uow(ctx.tenant) as tx:
    ref = await lock_ref(tx, engagement_id)
    await authorise(ctx, "request_item.create", ref.resource())
    item = await insert_request_item(tx.session, item_id=item_id, ...)
    tx.record("request_item.created", target=Target("request_item", item_id),
              after=Ref(engagement_id=engagement_id))
    tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
```

- One `async with uow(ctx) as tx:` per state change; write only through `tx.session`. The change, its audit events and its outbox rows commit together or not at all.
- No `record`, no commit: leaving the block without one raises `MissingAuditEvent` and nothing is written. Read-only work uses `tenant_session`. An idempotent repeat that records nothing therefore raises it; catch it where that is expected (`agents.fail_run`).
- No nesting: a `uow` inside a `uow` raises `RuntimeError` (a second connection could commit what the outer rolls back, or deadlock). Share the transaction by passing `tx` down (`item_ref(tx, ...)`, `fulfil_by_rule(tx, ...)`).
- Call `uow` from the service layer, never from a FastAPI `Depends` with `yield`, so the commit and `MissingAuditEvent` surface inside the request.
- Never `session.commit()`, `flush()` or `rollback()` outside `kernel/uow` (UOW-001); only the kernel uses `tenant_connection` and the relay engine (UOW-002). If `record` needs a server-generated id, `await tx.session.flush()` first.
- Authorise before writing: a rollback can undo the write but not a decision already acted on.

## Audit events

```python
tx.record(action, *, target=Target(type, id), before=Ref(...), after=Ref(...))
```

- `action` is `entity.verb_past` (`request_item.created`); `Target.type` is lower snake case.
- `Target.id` is a UUID or integer. `Ref(**fields)` keys are lower snake case (up to 40 characters); values are UUIDs, integers or SHA-256 fingerprints. Names, emails, descriptions or any free text raise `ValueError`: audit holds references, never contents (ADR-007, ADR-031).
- Tenant, actor and trace come from the context, not the caller: the row gets `actor_kind`, `actor_id` and `trace_id` (the current trace), and the database rejects a row whose tenant or actor differs from the session's.
- Record every state change, one event per entity changed (`request_list.created` and `request_item.created` in one call). Record nothing for a no-op (`insert_fulfilment` returned `None`).

## Domain events

```python
# modules/requests/events.py
class RequestItemCreated(DomainEvent):
    event_type: ClassVar[str] = "request_item.created"
    request_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
```

- Subclass `DomainEvent` in the module's `events.py`, set `event_type`, export from `api.py`. `event_id` is generated; it is the outbox row id and the dedupe key.
- Identifiers only. `tx.emit` raises `ValueError` for a Restricted or unclassified field; consumers load what they need under their own tenant context.
- Emit only what another module reacts to; an audit event is not a message.

## Tables

| Table | App access | Columns the unit of work writes |
|---|---|---|
| `audit_events` | insert only | `tenant_id`, `actor_kind`, `actor_id`, `action`, `target_type`, `target_id`, `before_ref`, `after_ref`, `trace_id` (`seq` is server-set) |
| `outbox` | insert only | `id` (= `event_id`), `tenant_id`, `event_type`, `payload`, `trace_context` (W3C `traceparent`); only `abacus_relay` updates `published_at`, `attempts`, `last_error`, `next_attempt_at` |

Both are in `schema_check.INSERT_ONLY_TABLES` (no UPDATE or DELETE for `abacus_app`) and owned by `kernel.uow` in `TABLE_OWNERS`; `APP_INSERT_COLUMNS` limits what the app may supply. Emitting the same event twice in one unit of work rolls it back.

## The relay

```python
# abacus/worker/__main__.py
relay = asyncio.create_task(run_relay(publisher(), stop))   # RoutingPublisher: handlers by event_type
# modules/agents/screenings.py (exported through api.py)
SUBSCRIPTIONS = {EVIDENCE_VERSION_CREATED: start_screening}
```

- The worker runs `run_relay` as role `abacus_relay` (reads every tenant's outbox, changes only delivery columns). If the relay task dies, the worker exits non-zero.
- At least once: an event is marked published only after `publish` returns; a crash republishes it with the same `event_id`.
- Fair per tenant: a pass claims at most `per_tenant` (10) events of one tenant and `batch` (25) overall, with `FOR UPDATE SKIP LOCKED`. A failure defers that tenant's later events in the pass.
- Failures back off exponentially (`2**attempts` seconds, capped at 3600) and are parked at `MAX_ATTEMPTS = 10`; logged as `outbox.publish_failed` with the exception class only. A malformed payload is a failure.
- No global order: `seq` is insert order, not commit order. Locks are held while publishing, so keep batches small; each handler is bounded by `HANDLER_TIMEOUT` (15 s) and each pass by `PASS_TIMEOUT` (120 s).
- A module subscribes with `SUBSCRIPTIONS: dict[str, Handler]` in `api.py` (`connections` has an empty one) and is listed in the worker's `MODULES`. Handlers take an `OutboxEvent`; publishing continues the emitting trace through `trace_context`.

## A consumer

- Handlers must be idempotent: a redelivery, or a later handler failing, runs them again. Deduplicate on the event.
- Rows: `agents.create_screening_run(tenant_id, evidence_version_id, source_event_id, requested_by)` inserts with `on_conflict_do_nothing(constraint="agent_runs_once_per_event")`; a repeat finds the existing run and records nothing.
- Workflows: `start_screening` uses `screening:<tenant_id>:<evidence_version_id>` as the workflow id with `USE_EXISTING` and suppresses `WorkflowAlreadyStartedError`, so a redelivery counts as delivered.
- Take inputs only from the event's identifiers; a malformed event should raise so the relay backs it off and parks it. Act for no one when the event names no initiator.

## Enforced by

| Point | Rule or test |
|---|---|
| No commit, flush or rollback outside the kernel | UOW-001 |
| `tenant_connection` and the relay engine only in the kernel | UOW-002 |
| No engines or raw connections; `tenant_session(ctx)` only | DB-001 |
| Tenant and actor settings only in `kernel.db` | TENANT-001 |
| Insert-only audit and outbox; relay privileges | `schema_check`, `test_unit_of_work.py`, `test_outbox_relay.py` |
| `MissingAuditEvent`, rollback, identifiers-only | `test_unit_of_work.py`, `test_uow_api.py` |

## Not yet

- No static check that a service which writes also records; `MissingAuditEvent` is a runtime failure, and nesting is too.
- No dead-letter view or replay for parked events.
- The worker holds the relay role, which reads every firm's outbox: an accepted risk (TASK-011 Q4).
