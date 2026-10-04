---
id: ADR-012
title: FastAPI backend with enforced layering
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
FastAPI is widely known by agents, async, and generates OpenAPI automatically. It does not impose structure, so structure is imposed by convention and tooling.

## Decision
The backend uses FastAPI. Each module follows the layering routes → service → repository. Routes are thin and contain no business logic. Services hold business rules. Repositories hold all database access. Every route declares a response model and depends on the auth context and a tenant-scoped database session.

## Options considered
### FastAPI with enforced layers — chosen
- Pros: Agent fluency; automatic OpenAPI; Pydantic-native
- Cons: Structure must be enforced by us
- Chosen.

### Django
- Pros: Batteries included
- Cons: Heavier; its ORM and patterns conflict with ADR-015 and ADR-018
- Rejected.

## Consequences
**Positive**
- Consistent, predictable code in every module

**Negative / costs accepted**
- Conventions must be maintained by tooling

## Enforcement
- import-linter layer contract: `routes` → `service` → `repository`; never the reverse
- Test introspects `app.routes` and fails if any route lacks the auth dependency or a response model
- Reference module in the walking skeleton is the pattern every module copies

## Guidance for agents
Keep routes thin; put rules in services.

**Do**
```python
@router.post('/request-items', response_model=RequestItemOut)
async def create(body: RequestItemIn, ctx: Ctx = Depends(auth_ctx)):
    return await service.create(ctx, body)
```

**Don't**
```python
@router.post('/request-items')
async def create(body: dict, db = Depends(get_db)):
    db.execute('INSERT ...')
```

## Revisit when
Never expected to change.

## Related
- ADR-008
- ADR-013
- ADR-020
