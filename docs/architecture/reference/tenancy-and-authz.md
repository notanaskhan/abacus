# Reference: tenancy and authorisation

The pattern every module copies (SPEC-000 §22). Binding rules: ADR-002, ADR-014, ADR-020, ADR-023, ADR-024, ADR-027, ADR-102.

## A route

```python
# modules/<module>/routes.py
from typing import Annotated
from fastapi import Depends
from abacus.modules.identity.api import AbacusRouter, AuthContext, Resource, authorise, current_context

router = AbacusRouter(prefix="/v1/engagements", tags=["engagements"])

@router.post("/{engagement_id}/request-items", action="request_item.create",
             response_model=RequestItemOut, status_code=201)
async def add_item(engagement_id: UUID, body: RequestItemIn,
                   ctx: Annotated[AuthContext, Depends(current_context)]) -> RequestItemOut:
    return await service.add_item(ctx, engagement_id, body)
```

- Exactly one action per route, from `docs/architecture/permission-matrix.yaml`.
- Export `router` from the module's `api.py` and add it to `ROUTERS` in `abacus/api/app.py`.
- Authentication is attached by the router. A route that returns a success without a successful `authorise` (or a `visible` filter) for its action becomes a 500.

## A service

```python
async def add_item(ctx: AuthContext, engagement_id: UUID, body: RequestItemIn) -> RequestItemOut:
    async with uow(ctx.tenant) as tx:
        ref = await engagements.lock_ref(tx, engagement_id)            # 404 outside the tenant
        await authorise(ctx, "request_item.create", ref.resource())    # before any write
        ...
        tx.record("request_item.created", target=Target("request_item", item.id))
```

- Authorise **before** any write: the guard can hide a response but can't undo a commit.
- `archived` comes from the row, never a literal (AUTHZ-003).
- Missing, or another firm's → 404 (row-level security makes them indistinguishable, so nothing leaks across firms). Found but denied → 403: existence within a firm isn't secret (TASK-008 design §3).
- For writes, resolve and share-lock the row inside the unit of work (`lock_ref`) and authorise there, so the check and the write see the same row.
- Build engagement resources with `ref.resource()` only: it carries `archived` and the engagement's `client_id`, which the wall check needs.

## Ethical walls (ADR-026, SPEC-002)

- `authorise` checks walls before roles, so a wall beats every role, firm admin included. The person checked is the user, the person who started an agent's run, or the person a system run acts for.
- A walled engagement answers **404**, with the same body as a missing engagement (`Forbidden(layer="wall")`, mapped in `abacus.api.app`).
- `visible()` adds the wall filter itself: nothing to do in a list query.
- Identity owns walls and engagements owns which client an engagement belongs to. `engagements.api` registers that lookup with `register_engagement_client` at import, so identity never imports engagements (dependency inversion, TASK-016 Q1). Without the registration, a walled person is denied everything engagement-scoped (fail closed).
- Walls are read once per request and live on every step outside one (workers), so a new wall applies from the next request or step.

## A list

```python
q = select(Engagement).where(visible(ctx, "engagement.read_metadata", Engagement.id))
```

- Every repository list method applies `visible()` with the route's read action (ADR-027, ADR-102).
- `tenant_session(ctx.tenant)` scopes to the tenant (RLS); `visible` narrows to what the actor may see.

## Never

- Read roles from tokens, compare roles, or read `ctx.firm_role` outside identity (ADR-020, ADR-029).
- Take a tenant from a request body, path or header (ADR-002). The tenant is `ctx.tenant_id`.
- Build an `AuthContext`, or copy one with changes.
