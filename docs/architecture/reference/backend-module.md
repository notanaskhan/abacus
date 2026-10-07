# Reference: backend module layout, layering, public API

The pattern every module copies (SPEC-000 §22). Binding rules: ADR-008, ADR-012, ADR-013, ADR-031, ADR-101, ADR-102, ADR-103. Worked example: `backend/src/abacus/modules/requests`. Authorisation is in [tenancy-and-authz.md](tenancy-and-authz.md); transactions, audit and events in [unit-of-work.md](unit-of-work.md).

## Layout

```
modules/requests/
  api.py         the only file other modules may import
  routes.py      AbacusRouter, request/response models
  service.py     rules: authorise, uow, audit, emit
  repository.py  queries on this module's tables only
  models.py      SQLAlchemy models (tables this module owns)
  events.py      DomainEvent subclasses it publishes
  README.md      public interface and rules
```

Layering is `routes → service → repository` (AGENTS.md). Routes translate HTTP and call one service function; services hold rules; repositories hold SQL. A module with no events has no `events.py`; one with no HTTP surface has no `routes.py` (`ledger`, `organisations`).

## Public API

```python
# modules/requests/api.py
"""Public interface of the requests module; other modules import only this (ADR-008)."""
from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.routes import router
from abacus.modules.requests.service import FulfilmentRef, fulfil_by_rule, item_ref
__all__ = ["FulfilmentRef", "RequestItemCreated", "fulfil_by_rule", "item_ref", "router"]
```

- Export the `router`, the service functions, the small frozen dataclasses other modules need (`RequestItemRef`, `FulfilmentRef`) and the events others subscribe to. Never export ORM models or repository functions; return dataclasses, not rows.
- A function that joins the caller's transaction takes `tx: UnitOfWork` first (`item_ref(tx, id)`, `fulfil_by_rule(tx, ctx, ...)`); a read takes a `TenantContext` or `AuthContext`.
- A module with workflows or event handlers also exports `WORKFLOWS` (each workflow's work class), `ACTIVITIES`, `SUBSCRIPTIONS` from `api.py` (`connections`, `agents`); the worker composes them. Workflows start only through `kernel.dispatch` (ADR-071).
- Outside a module, import `abacus.modules.<m>.api` only, never `abacus.modules` itself (BOUND-001).

## Dependencies and tables

```python
# backend/src/abacus_tools/quality/banned_patterns.py
MODULE_DEPENDENCIES = {"identity": frozenset(), "requests": frozenset({"identity", "engagements"}), ...}
# backend/src/abacus_tools/quality/schema_check.py
TABLE_OWNERS = {"request_lists": "requests", "request_items": "requests", "fulfilments": "requests", ...}
```

- Dependencies point one way (BOUND-002). A module not listed may use `identity` only. A new edge edits `MODULE_DEPENDENCIES`, which is protected (`abacus_tools/quality/`).
- A module names only tables it owns: `__tablename__`, `Table(...)` and raw SQL strings (OWN-001). Need another module's data? Call its `api.py`.
- A new table is added to `TABLE_OWNERS` in the same change as its migration; `schema_check` fails a table with no owner and an owner with no table (ADR-103). Migrations use `tenant_table(op, name)`, or `insert_only(op, name)` for immutable tables, which also go in `INSERT_ONLY_TABLES` (`fulfilments` does). `APP_INSERT_COLUMNS` lists the columns the app may supply on insert.

## Routes

```python
# modules/requests/routes.py
router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/request-items", tags=["requests"])

class RequestItemIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)
    description: Annotated[MultiLineText, Field(min_length=1, max_length=2000), classified("confidential")]

@router.post("", action="request_item.create", response_model=RequestItemOut, status_code=201)
async def create_request_item_route(engagement_id: UUID, body: RequestItemIn, ctx: Ctx) -> RequestItemOut:
    return _out(await add_request_item(ctx, engagement_id, NewRequestItem(...)))
```

- One action per route, a `response_model`, an explicit status code; no route outside `AbacusRouter` (ROUTE-001). See tenancy-and-authz.md.
- Input models are `frozen`, `extra="forbid"`, length-bounded, with `SingleLineText`/`MultiLineText` for client text (client content is hostile). Output models are validated from the service's dataclass (`model_validate(..., from_attributes=True)`), not coerced.
- Every Pydantic field carries `classified("restricted" | "confidential" | "internal" | "public")` (ADR-031): request and response models and every `DomainEvent`. `tests/unit/kernel/test_classification.py` walks every model under `abacus` and fails on an untagged field. SQLAlchemy models are not Pydantic and are not tagged.
- Add the module's router to `ROUTERS` in `abacus/api/app.py` (protected). The app serves no docs UI; the OpenAPI document comes from `app.openapi()`.

## Service and repository

```python
# service.py
async with uow(ctx.tenant) as tx:
    ref = await lock_ref(tx, engagement_id)                       # engagements.api; 404 outside the tenant
    await authorise(ctx, "request_item.create", ref.resource())   # before any write
    item = await insert_request_item(tx.session, ...)
    tx.record("request_item.created", target=Target("request_item", item_id), after=Ref(engagement_id=engagement_id))
    tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))

# repository.py
select(RequestItem, latest).where(
    RequestItem.engagement_id == engagement_id,
    visible(ctx, "request_item.read", RequestItem.engagement_id))
```

- Writes: `uow` in the service, `authorise` before the first write, `tx.record` for each change (unit-of-work.md). Reads: `authorise` on the parent resource, then `tenant_session(ctx.tenant)`.
- Repositories take a session and return rows or scalars; they never commit, authorise or call other modules. Idempotent inserts use `on_conflict_do_nothing(...).returning(id)` and return `None` on a repeat (`insert_fulfilment`).
- A repository function that lists rows (name starts `list_`, `all_`, `search_`, or it calls `.all()`) applies `visible(ctx, "<read action>", column)` inside `.where(...)` with a literal read action from the matrix (LIST-001, ADR-102). A lookup for rows the caller already authorised goes in `LIST_EXEMPT` with review (`items_fulfilled_by`).
- Domain errors are `kernel.errors` types: `NotFound` (404) and `DomainConflict` subclasses with a fixed `code` (409, e.g. `ItemNotFulfillable`). Messages never echo request or database values.

## Contract and generated client

`make generate` writes `packages/api-client/openapi.json` from `abacus.api.export_openapi` and regenerates the TypeScript client; `make check` fails if the committed client differs. A route change commits the regenerated client (see [frontend-feature.md](frontend-feature.md)). `tests/unit/api/test_openapi.py` checks that every operation has a unique id, an action and the documented error responses.

## The module README

`modules/<m>/README.md` is short and changes with the code:

```
# requests
One line of purpose, in glossary terms. Owns `request_lists` and `request_items` (ADR-103).
## Public interface (`api.py`)   each export, its action, what it returns
## Rules                         invariants; audit and outbox event names; who authorises
```

## Enforced by

| Point | Rule or test |
|---|---|
| Only `api.py` imported across modules | BOUND-001 |
| One-way dependencies | BOUND-002, `MODULE_DEPENDENCIES` |
| Own tables only; every table owned | OWN-001, `schema_check` |
| Lists use `visible()` | LIST-001 |
| Routes through `AbacusRouter`, one action | ROUTE-001, `test_app_gates.py`, `test_openapi.py` |
| Fields classified | `test_classification.py` |
| No commits outside the unit of work | UOW-001 |

## Not yet

- No module template or generator: copy `requests`.
- The README format is convention; no tool checks it.
