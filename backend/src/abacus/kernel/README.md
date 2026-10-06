# abacus.kernel — shared kernel

Not a module (ADR-101). Every module uses it; it never imports a module.

| Package | Use it for | Rule |
|---|---|---|
| `kernel.db` *(red, protected)* | `tenant_session(ctx)` for every query; `TenantContext` | The only code that opens connections (DB-001). Never commits — writes go through the unit of work (TASK-006). |
| `kernel.uow` *(red, protected)* | Every state change: `async with uow(ctx) as tx:` — `tx.session`, `tx.record(action, target=..., before=Ref(...), after=Ref(...))`, `tx.emit(DomainEvent)` | Change, audit events and outbox rows commit together or not at all; no `record` ⇒ no commit (`MissingAuditEvent`). Audit holds references, never contents; events carry identifiers only. |
| `kernel.uow.relay` *(protected)* | `relay_once(publisher)` in the worker | At-least-once delivery as `abacus_relay`; consumers deduplicate by `event_id`. |
| `kernel.db.migration` *(protected)* | `tenant_table(op, name)` in every migration that creates a tenant table; `insert_only(op, name)` for evidence and ledger tables | `schema_check` fails any table without forced row-level security and the `tenant_isolation` policy. |
| `kernel.classification` | `Annotated[T, classified("restricted" \| "confidential" \| "internal" \| "public")]` on every Pydantic field | A unit test fails on any unclassified field (ADR-031). |
| `kernel.logging` | `get_logger(__name__).info("event.name", key=value)` | Refuses Restricted data at any depth, Decimals and arbitrary objects (ADR-022). |
| `kernel.config` | `settings()` | Local and test default to `docker compose`; elsewhere every connection setting is required. |

Database roles (`backend/migrations/bootstrap.sql`, protected): `abacus_owner` owns tables and runs migrations; `abacus_app` is what the API and worker use — not an owner, no `BYPASSRLS`; `abacus_relay` bypasses row-level security but can only read the outbox and mark delivery. Row-level security is forced, so the owner is bound by it too.
