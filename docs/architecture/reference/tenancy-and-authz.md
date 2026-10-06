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
    engagement = await engagements.get_ref(ctx, engagement_id)       # tenant_session, RLS-scoped
    await authorise(ctx, "request_item.create",
                    Resource.engagement(ctx.tenant_id, engagement.id, archived=engagement.archived))
    async with uow(ctx.tenant) as tx:                                 # write only after authorise
        ...
        tx.record("request_item.created", target=Target("request_item", item.id))
```

- Authorise **before** any write: the guard can hide a response but can't undo a commit.
- `archived` comes from the row, never a literal (AUTHZ-003).
- A missing row and a denied row should both answer 403 or 404 consistently, so that existence never leaks across engagements.

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
