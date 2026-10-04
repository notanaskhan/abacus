---
id: ADR-027
title: In-house policy-as-code with a protected permission matrix
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Permissions must be consistent, tested and resistant to silent loosening by coding agents. The relationship model is modest and lives naturally in Postgres.

## Decision
Authorisation is an in-house module. Relationships live in Postgres. Rules are declared in `docs/architecture/permission-matrix.yaml` (role × action × condition → decision). Tests are generated from the matrix, covering every allow and deny. The module exposes `authorise(ctx, action, resource)` for single resources and `visible(ctx, resource_type)` returning a query filter for lists. Every API route declares exactly one action.

## Options considered
### In-house with matrix — chosen
- Pros: One database; no sync bugs; fully testable
- Cons: We maintain it
- Chosen.

### Relationship-based authorisation service
- Pros: Scales to complex graphs
- Cons: Separate store requiring dual writes
- Rejected for now.

### Stateless policy engine
- Pros: Policy-as-code
- Cons: Another service
- Rejected for now.

### Hosted authorisation
- Pros: Fast
- Cons: Vendor dependency for the most critical control
- Rejected.

## Consequences
**Positive**
- Every permission is tested, including denials
- Permission changes are visible diffs

**Negative / costs accepted**
- Module maintenance

## Enforcement
- The matrix is a protected path; changes require human approval
- Generated tests run on every change
- Test inspects every repository list method and fails if `visible()` is not applied
- Route test fails if a route declares no action or an action not in the matrix

## Guidance for agents
Declare the action on the route; apply `visible` in list queries.

**Do**
```python
@router.get('/engagements/{id}/request-items', action='request_item.read')
async def list_items(...):
    q = select(RequestItem).where(visible(ctx, RequestItem))
```

**Don't**
```python
@router.get('/engagements/{id}/request-items')
async def list_items(...):
    return await repo.all()
```

## Revisit when
Authorisation checks become a performance bottleneck, or relationship complexity outgrows Postgres modelling.

## Related
- ADR-020
- ADR-023
