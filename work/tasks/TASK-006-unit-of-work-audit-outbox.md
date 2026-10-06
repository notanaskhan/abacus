---
id: TASK-006
title: Unit of work, audit events and outbox
spec: SPEC-000
acceptance_criteria: [AC-4, AC-20]
risk_zone: red
status: done
branch: task-006-uow
worktree:
created: 2026-10-06
updated: 2026-10-06
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
`abacus.kernel.uow`: every state change commits together with its audit events and domain events, atomically, in one tenant-scoped transaction; the unit of work refuses to commit without an audit event; audit events are insert-only; a relay publishes the outbox at least once, and consumers can deduplicate by event ID (ADR-007, ADR-018).

## Scope
**In**
- `abacus.kernel.db.tenant_connection(ctx)` — the tenant-scoped connection the unit of work owns (no commit inside `kernel.db`)
- `abacus.kernel.uow` — `uow(ctx)`, `record(...)`, `emit(...)`, `DomainEvent`, commit/rollback rules
- Migration `0002_audit_events_and_outbox`: `audit_events` and `outbox` tables
- Relay role `abacus_relay` (bootstrap) and `abacus.kernel.uow.relay` with a `Publisher` protocol and an in-memory publisher for tests
- `schema_check` additions for the relay role and the two insert-only tables
- Tests from an independent session (contract below)

**Out**
- Reading the audit trail (`audit_event.read`, the `audit_trail` module's API) — later
- Per-tenant hash chaining of audit events (ADR-007 follow-up)
- Publishing to Temporal (TASK-010/011 supply that `Publisher`); running the relay in the worker process (TASK-010)
- Trace IDs (TASK-013 fills the column; it stays `NULL` until then)
- The "every service command writes an audit event" registry test — there are no service commands until TASK-008, which adds it

## Context to load
- ADR-007, ADR-018, ADR-014, ADR-031, ADR-101; glossary *Audit event*, *Domain event*, *Outbox*, *Unit of work*
- `backend/src/abacus/kernel/db/`, `backend/migrations/bootstrap.sql`, `backend/src/abacus_tools/quality/schema_check.py`
- TASK-005 progress log (why `tenant_session`'s commit is inert)

## Plan
- [x] Plan approved by human (founder, 2026-10-06: "approved") — **red: founder reviews the diff line by line before merge**
- [x] Approval file `work/approvals/TASK-006.yaml` written by the agent at the founder's instruction (2026-10-06)
- Approved by founder: paths under *Approval file text*, expires 2026-10-27
- [x] Q1–Q4 answered: all recommendations approved (2026-10-06)

### Design (for founder review)

**1. The unit of work owns its transaction.** `kernel.db` gains `tenant_connection(ctx)`: the same connection setup as `tenant_session` (app role, `RESET`, transaction-local tenant and actor settings) but it yields the `AsyncConnection` and never commits or rolls back — the caller owns the transaction. Only `kernel.uow` may call it (TENANT-001 and UOW-001 already confine settings and commits to these packages; a new banned pattern **UOW-002** forbids importing `tenant_connection` outside `kernel.uow`).

**2. API** (async, matching ADR-018's shape):
```python
async with uow(ctx) as tx:
    item = await tx.session.get(RequestItem, item_id)        # AsyncSession in the uow's transaction
    item.status = "received"
    tx.record("request_item.received", target=Target("request_item", item.id),
              before=Ref(version=3), after=Ref(version=4))
    tx.emit(RequestItemReceived(request_item_id=item.id))
```
- On normal exit: flush the session, insert the audit events and outbox rows, **commit**.
- On exception: roll back; nothing is written, not even audit events.
- **No audit event ⇒ no commit.** Exiting with zero `record(...)` calls raises `MissingAuditEvent` and rolls back (ADR-007/018). Read-only work uses `tenant_session`, never `uow`.
- Actions must match `^[a-z][a-z_]*\.[a-z][a-z_]*$` (`<entity>.<verb_past>`); targets are `(type, id)`; `before`/`after` are references (ids, versions, fingerprints), never record contents — so Restricted data never enters the audit trail.
- `DomainEvent` is a Pydantic base class with `event_type: ClassVar[str]` and an `event_id` generated at creation; every field classified, and **no Restricted fields** — events carry identifiers, consumers load data under their own tenant context. `emit` validates this.

**3. Tables** (migration `0002`, both tenant tables via `tenant_table` and both `insert_only`):
| `audit_events` | `outbox` |
|---|---|
| `id uuid PK DEFAULT gen_random_uuid()` | `id uuid PK` (= `event_id`) |
| `tenant_id uuid NOT NULL` | `tenant_id uuid NOT NULL` |
| `seq bigint GENERATED ALWAYS AS IDENTITY` (order) | `seq bigint GENERATED ALWAYS AS IDENTITY` |
| `occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()` | `occurred_at timestamptz NOT NULL DEFAULT clock_timestamp()` |
| `actor_kind text NOT NULL CHECK (actor_kind IN ('human','agent','system'))`, `actor_id text NOT NULL` | `event_type text NOT NULL` |
| `action text NOT NULL CHECK (action ~ '^[a-z][a-z_]*\.[a-z][a-z_]*$')` | `payload jsonb NOT NULL` |
| `target_type text NOT NULL`, `target_id text NOT NULL` | `published_at timestamptz NULL`, `attempts int NOT NULL DEFAULT 0`, `last_error text NULL` |
| `before_ref jsonb NULL`, `after_ref jsonb NULL`, `trace_id text NULL` | index on `(seq) WHERE published_at IS NULL` |

Actor columns are written from `ctx` **and** checked by the database: `CHECK (actor_kind = current_setting('app.actor_kind', true) AND actor_id = current_setting('app.actor_id', true))`, so an audit event can't claim a different actor than the transaction's. Both tables are added to `INSERT_ONLY_TABLES`.

**4. The relay** (Q1). Forced RLS confines every session to one tenant, but the relay must read every tenant's unpublished events. Proposal: role **`abacus_relay`** (bootstrap) with `BYPASSRLS` and privileges on nothing but `outbox`: `SELECT` and `UPDATE (published_at, attempts, last_error)`, granted in migration 0002. `relay_once(publisher, batch=100)`:
```sql
SELECT id, tenant_id, event_type, payload FROM outbox
WHERE published_at IS NULL ORDER BY seq LIMIT :batch FOR UPDATE SKIP LOCKED
```
publish each (`await publisher.publish(event)`), then `UPDATE outbox SET published_at = clock_timestamp()` — or `attempts = attempts + 1, last_error = <type only>` on failure — and commit. **At least once**: a crash between publish and commit republishes; consumers deduplicate by `event_id` (ADR-018). Several relays can run concurrently (`SKIP LOCKED`). `Publisher` is a protocol; tests use `InMemoryPublisher`; TASK-010/011 add the Temporal one.

**5. `schema_check` additions**: `abacus_relay` must exist without `SUPERUSER`/`CREATEROLE`/`CREATEDB`, own nothing, and hold privileges on no table but `outbox` (and there only `SELECT` + column `UPDATE`); `audit_events` and `outbox` insert-only for `abacus_app`.

### Steps
1. [x] Protect first: `backend/src/abacus/kernel/uow/**` is already protected (hook, CODEOWNERS) — verify; nothing new to protect.
2. [x] `bootstrap.sql`: `abacus_relay` role (+ local password in `bootstrap-local.sql`); settings `relay_database_url`.
3. [x] `kernel/db`: `tenant_connection(ctx)`, `relay_engine()`.
4. [x] Migration `0002`: tables, constraints, RLS, insert-only, relay grants; update `INSERT_ONLY_TABLES` and relay checks in `schema_check`.
5. [x] `kernel/uow`: `uow`, `UnitOfWork`, `record`, `emit`, `Target`, `Ref`, `DomainEvent`, `MissingAuditEvent`; `kernel/uow/relay.py`: `Publisher`, `OutboxEvent`, `relay_once`, `InMemoryPublisher`.
6. [x] Banned pattern UOW-002; kernel README.
7. [x] Independent tests; `make check`; gate-break (an audit event row updated or deleted by the app fails; a uow with no `record` raises; relay privileges on another table fail `schema_check`).

### Interface contract (tests written independently — ADR-078)
- `from abacus.kernel.uow import uow, UnitOfWork, Target, Ref, DomainEvent, MissingAuditEvent`; `from abacus.kernel.uow.relay import Publisher, OutboxEvent, InMemoryPublisher, relay_once`.
- `uow(ctx)` → `AsyncContextManager[UnitOfWork]`; `tx.session: AsyncSession`; `tx.record(action: str, *, target: Target, before: Ref | None = None, after: Ref | None = None) -> None`; `tx.emit(event: DomainEvent) -> None`. `Target(type: str, id: str | UUID)`; `Ref(**fields: str | int | UUID)` → JSON object.
- Invalid action → `ValueError` at `record`; event with a Restricted (or unclassified) field → `ValueError` at `emit`; zero `record` calls → `MissingAuditEvent` at exit, nothing written.
- Proven against a real database (`migrated_db`, probe tenant table created in the test through `tenant_table`):
  - (AC-4) a change, its audit event and its outbox row commit together, or none of them (exception inside the block, `MissingAuditEvent`, a failing audit insert)
  - audit rows carry the context's tenant and actor; inserting an audit row with another actor or tenant fails
  - `abacus_app` cannot `UPDATE`/`DELETE` `audit_events` or `outbox`; tenant B's `uow` can't see tenant A's audit rows
  - `relay_once` publishes every tenant's unpublished events once, in `seq` order, marks them published; a publisher failure leaves the event unpublished with `attempts` incremented; two concurrent relays never publish the same event twice in one pass; a crash before commit (simulated) republishes the event with the **same** `event_id`
  - `abacus_relay` can read `outbox` only — no other table, no `UPDATE` of `payload`
- `schema_check` reports: relay with privileges on another table; relay `UPDATE` on `payload`; app `UPDATE`/`DELETE` on `audit_events` or `outbox`.

#### Contract revision 1 (2026-10-06, from both stage 4 reviews)
**Database**
- Column-level INSERT for the app (new helper `insert_columns(op, table, columns)` in `kernel.db.migration`: one `REVOKE INSERT ON <t> FROM abacus_app` then one `GRANT INSERT (<c1>, <c2>, …) ON <t> TO abacus_app`, columns in the given order, same name validation as `tenant_table`). `audit_events`: `tenant_id, actor_kind, actor_id, action, target_type, target_id, before_ref, after_ref, trace_id` — so the app can't set `id`, `seq` (no `OVERRIDING SYSTEM VALUE`), or `occurred_at`. `outbox`: `id, tenant_id, event_type, payload` — so it can't insert a row already published, attempted or failed. `schema_check` reports `<t>: abacus_app may INSERT <t>.<column>` for any other insertable column of an insert-only table.
- Actor check: `actor_kind IS NOT DISTINCT FROM NULLIF(current_setting('app.actor_kind', true), '')` (same for `actor_id`) — an unset setting now fails.
- `target_id` must be a UUID or digits (CHECK); `last_error` must look like an exception class name (`^[A-Za-z_][A-Za-z0-9_.]{0,199}$`).
- `outbox` primary key is `(tenant_id, id)` — tenants can't collide on, or probe, each other's event IDs. Consumers deduplicate on `(tenant_id, event_id)`.
- `outbox.next_attempt_at timestamptz NULL` (relay-updatable). `schema_check`: relay updatable columns are `published_at, attempts, last_error, next_attempt_at`; relay with any sequence privilege or membership in any role is reported (`abacus_relay: has <PRIVILEGE> on sequence <name>`, `abacus_relay: is a member of <role>`).
- Known limit, stated honestly: the app role controls its own session settings, so the database actor/tenant checks catch application **bugs**, not malicious SQL in application code. Static rules close the code paths: TENANT-001 now covers every literal containing `app.tenant_id` **or `app.actor_`**.

**Unit of work**
- Nested `uow` raises `RuntimeError("nested unit of work")` (ContextVar), nothing written by the inner one.
- `Target(type, id)`: `type` matches `^[a-z][a-z_]*$`; `id` is a `UUID`, an `int`, or a string that is a UUID or all digits — else `ValueError`. `Ref(**fields)`: keys match `^[a-z][a-z_]{0,39}$`; values are `UUID`, `int`, or a 64-character lowercase hex fingerprint — else `ValueError`. References can't carry free text.

**Relay**
- `relay_once(publisher, batch=25) -> RelayResult(published: int, failed: int, deferred: int)`; never raises for a publisher error or a malformed payload (counted as failed); a `BaseException` (crash, cancel) still propagates and rolls back the pass.
- Claims only rows with `published_at IS NULL AND attempts < MAX_ATTEMPTS (10) AND (next_attempt_at IS NULL OR next_attempt_at <= now())`, ordered by `seq`.
- On a failure: `attempts + 1`, `last_error = <exception class name>`, `next_attempt_at = now() + min(2^attempts, 3600) seconds`; **the rest of that tenant's events in this pass are deferred** (not published, not touched) so one tenant's events don't overtake its failed one; other tenants proceed. After `MAX_ATTEMPTS` the event is parked (never claimed again; visible by `attempts >= 10`).
- Each failure is logged as `outbox.publish_failed` with `event_id`, `tenant_id`, `event_type`, `attempts`, `error` (class name) — never the payload.
- Ordering: per tenant within a pass, best effort across passes; `seq` is insert order, not commit order. Consumers must be idempotent and must not assume global order.
- UOW-002 also covers `relay_engine` and `configure_relay_engine` (the BYPASSRLS engine) — allowed only in `kernel/db`, `kernel/uow`, `tests/integration`.

### Approval file text
```yaml
task: TASK-006
approved_by: founder
expires: 2026-10-27
paths:
  - backend/migrations/bootstrap.sql
  - backend/migrations/bootstrap-local.sql
  - backend/src/abacus/kernel/db/**
  - backend/src/abacus/kernel/uow/**
  - backend/src/abacus_tools/quality/schema_check.py
  - backend/src/abacus_tools/quality/banned_patterns.py
  - backend/tests/unit/quality/test_banned_patterns.py
reason: TASK-006 — unit of work, audit events, outbox and relay
```

## Definition of done
- [ ] All listed ACs have passing tests that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] Security scan passes; no secrets committed
- [ ] No new dependencies, or each one approved and listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation — tenant-scoped; no endpoints
- [ ] AI calls — n/a
- [ ] Module README and relevant docs updated (kernel README)
- [ ] Decisions below reviewed; ADR raised where needed
- [ ] Both CI jobs pass on the PR; reviewed line by line by the founder

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| none | | | |

## Progress log
- `2026-10-06` — Created from the SPEC-000 breakdown approved by the founder.
- `2026-10-06` — TASK-005 merged (PR #5). Design drafted for founder review (red task). No code.

- `2026-10-06` — Implemented per the approved design. Probe end to end: uow commit writes change + audit (actor from context, reference not content) + outbox; `MissingAuditEvent` writes nothing; relay publishes once and marks published. Independent tests (Sonnet): 27 uow, 19 relay, 9 API, 8 schema_check, 4 UOW-002, config updated for the new required `relay_database_url` (contract change; their test, updated by them). DB-001 exclusions of the approved kind for `test_unit_of_work.py` and `test_outbox_relay.py` (owner/relay engines for probe tables). `sensitive_paths` moved from `kernel.logging` into `kernel.classification` so `emit` and the logger share one check. `make check` exit 0: 1,499 unit + 176 integration, coverage 97 %.

- `2026-10-06` — Both stage 4 reviews addressed (contract revision 1): migration **0003** (0002 is immutable once it exists) — column-level INSERT for the app, NULL-safe actor CHECK, target/last_error CHECKs, outbox PK `(tenant_id, id)`, `next_attempt_at`; uow refuses nesting, `Target`/`Ref` identifiers only; relay backoff (cap 1 h), parking after 10 attempts, per-tenant deferral within a pass, `RelayResult`, `outbox.publish_failed` log; TENANT-001 covers `app.actor_*`; UOW-002 covers `relay_engine`/`configure_relay_engine`; schema_check checks app insert columns (where declared in `APP_INSERT_COLUMNS`), relay sequences and role membership; `migrated_db` exposes `superuser_dsn`. Relay backoff/deferral is a design change beyond the approved design — flagged for the founder's line-by-line review.

- `2026-10-06` — Independent tests updated for revision 1 (rollback test moved to its own file; superuser plants malformed payload; TENANT-001 message updated — a changed existing test, contract change). One narrow UOW-001 exclusion for `tests/integration/test_uow_session_rollback.py`. `make check` exit 0: 1,644 unit + 238 integration, coverage 97 %.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The unit of work owns its transaction through `tenant_connection`, not `tenant_session` | `tenant_session` is read-only by design (TASK-005) | no |
| No audit event ⇒ no commit; read paths use `tenant_session` | ADR-007/018 enforcement, fail closed | no |
| Audit stores references, not record contents | Restricted data never enters the audit trail (ADR-031) | no |
| Domain events carry identifiers only | Events travel to Temporal and other modules; consumers load data in their own tenant context | no |
| Relay role with `BYPASSRLS` limited to the outbox | The only way one process reads every tenant's events under forced RLS | Q1 |

## Gotchas and discoveries
- From TASK-005 review: `tenant_session`'s `session.commit()` is inert by design (rollback-only join). The unit of work must own its transaction (open its own tenant transaction in `kernel.db`, write, audit, outbox, commit) — never build on `tenant_session`'s commit. `app.actor_kind` / `app.actor_id` are set per transaction for the audit trail.

## Questions for the human
- [x] **Q1 — Relay role.** Approved 2026-10-06. `abacus_relay` with `BYPASSRLS`, privileges only on `outbox` (`SELECT`, `UPDATE` of three status columns). Alternatives: iterate tenants under RLS (needs a firm list the relay can read — another cross-tenant read), or a `SECURITY DEFINER` function (FORCE RLS binds the owner too, so it would need a bypass role anyway). **Recommendation:** the relay role.
- [x] **Q2 — No audit event, no commit.** Approved 2026-10-06. Strict rule: a `uow` with zero `record` calls never commits, even if it changed nothing. **Recommendation:** yes — read-only work uses `tenant_session`.
- [x] **Q3 — Database-checked actor.** Approved 2026-10-06. Audit rows must match the transaction's `app.actor_*` settings (CHECK constraint). **Recommendation:** yes — a bug can't attribute an action to someone else.
- [x] **Q4 — Domain events carry no Restricted fields.** Approved 2026-10-06. **Recommendation:** yes.

## Handoff
- **Current state:** Done. PR #6 merged (rebase) 2026-10-06 after founder review and green CI; approval file deleted.
- **Exact next step:** none — TASK-007.
