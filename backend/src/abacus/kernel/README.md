# abacus.kernel — shared kernel

Not a module (ADR-101). Every module uses it; it never imports a module.

| Package | Use it for | Rule |
|---|---|---|
| `kernel.db` *(red, protected)* | `tenant_session(ctx)` for every query; `TenantContext` | The only code that opens connections (DB-001). Never commits — writes go through the unit of work (TASK-006). |
| `kernel.uow` *(red, protected)* | Every state change: `async with uow(ctx) as tx:` — `tx.session`, `tx.record(action, target=..., before=Ref(...), after=Ref(...))`, `tx.emit(DomainEvent)` | Change, audit events and outbox rows commit together or not at all; no `record` ⇒ no commit (`MissingAuditEvent`). Audit holds references, never contents; events carry identifiers only. |
| `kernel.uow.relay` *(protected)* | `relay_once(publisher)` in the worker | At-least-once delivery as `abacus_relay`; consumers deduplicate by `event_id`. |
| `kernel.db.migration` *(protected)* | `tenant_table(op, name)` in every migration that creates a tenant table; `insert_only(op, name)` for evidence and ledger tables | `schema_check` fails any table without forced row-level security and the `tenant_isolation` policy. |
| `kernel.classification` | `Annotated[T, classified("restricted" \| "confidential" \| "internal" \| "public")]` on every Pydantic field | A unit test fails on any unclassified field (ADR-031). |
| `kernel.logging` | `get_logger(__name__).info("event.name", key=value)` | Refuses Restricted data at any depth, Decimals and arbitrary objects (ADR-022). Adds `trace_id`/`span_id`; `error=exc` logs the class name only (TASK-013). |
| `kernel.telemetry` | `configure_tracing("abacus-api")`, `tracer(__name__)`, `current_traceparent()`/`continue_trace()` | One trace across processes; every exporter is wrapped in `ScrubbingExporter` (allowlisted attributes, no exception text) (ADR-022, TASK-013). |
| `kernel.metrics` | `configure_metrics("abacus-worker")`, `meter(__name__)`, `in_memory_reader()` | Metrics with allowlisted attribute keys only and no exemplars; OTLP when `otlp_endpoint` is set (ADR-094, SPEC-003). |
| `kernel.temporal_metrics` | `ScheduleToStartInterceptor` | Each activity's schedule-to-start latency by work class (`abacus.schedule_to_start`). |
| `kernel.work_class` | `WorkClass`, `WORK_CLASSES` | The four work classes (ADR-071); a leaf module. Limits per class: `settings().work_classes`. |
| `kernel.slots` | `acquire(tenant, holder, engagement_id, work_class)`, `renew`, `release(tenant_id, holder)`, `current_holder()`, `current_class()` | Work slots: per-firm and per-engagement caps with fair hand-out (ADR-071, SPEC-003). A platform ledger reached only through SECURITY DEFINER functions (migration 0013); commits without audit events (founder decision 2026-10-07), the one exception to UOW-001/UOW-002. |
| `kernel.dispatch` | `dispatch(Workflow, input, id=..., ...)`, `register_work_classes(WORKFLOWS)`, `queue_for(work_class)` | The only way to start a workflow: it runs on its work class's queue, `<base>-<class>` (ADR-071, SPEC-003). DISPATCH-001 bans `start_workflow` and `task_queue=` elsewhere. |
| `kernel.error_tracking` | `configure_error_tracking("abacus-api")`, `report(exc, route=…)`, `ReportingInterceptor()` | Sentry only with a DSN; every event rebuilt from an allowlist (`scrub`) (ADR-022, ADR-031, TASK-013). |
| `kernel.config` | `settings()` | Local and test default to `docker compose`; elsewhere every connection setting is required. |

Database roles (`backend/migrations/bootstrap.sql`, protected): `abacus_owner` owns tables and runs migrations; `abacus_app` is what the API and worker use — not an owner, no `BYPASSRLS`; `abacus_relay` bypasses row-level security but can only read the outbox and mark delivery. Row-level security is forced, so the owner is bound by it too.

## Unit of work rules (TASK-006)

- Call `uow` from the service layer, never from a FastAPI `Depends` with `yield`: the commit and `MissingAuditEvent` must surface inside the request, not after the response.
- No nesting: a `uow` inside a `uow` raises.
- Need a server-generated id for `record`? `await tx.session.flush()` first.
- `Target` and `Ref` take identifiers only (UUIDs, integers, SHA-256 fingerprints) — never names, emails or text.
- Domain events carry identifiers only; consumers load data under their own tenant context and deduplicate on `(tenant_id, event_id)`.

## Relay semantics

At least once; failures back off exponentially (capped at one hour) and are parked after 10 attempts (`attempts >= 10`, logged as `outbox.publish_failed`); a tenant's later events wait behind its failed one within a pass; no global order — `seq` is insert order, not commit order. Locks are held while publishing, so keep batches small.

## Known limit

The app role sets its own session settings, so the database checks on tenant and actor catch application bugs, not malicious SQL in application code. TENANT-001 confines those settings to `kernel.db`; UOW-001/UOW-002 confine commits and the relay engine to `kernel.uow`.

## Feature flags (SPEC-011)
`kernel.flags.flag(tenant, FLAG)` (and `flag_enabled` / `flag_variant`) reads a firm's value for a flag in `docs/architecture/feature-flags.yaml`, generated into `kernel/_flags.py`.
- Values are cached for 30 seconds.
- On any error the registry default is returned.
- Operators set values with `make flag` (audited).

## Actor kinds
`TenantContext.actor_kind` is one of `human`, `agent`, `system` or `support` (a break-glass staff member, SPEC-012). Audit events record it.
