---
id: ADR-014
title: PostgreSQL with shared schema and row-level security
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
Tenant isolation is the most critical security property of the platform. A single bug in application-level scoping must not expose one firm's data to another.

## Decision
Managed PostgreSQL. Every tenant-owned table has a NOT NULL `tenant_id`. Isolation is enforced twice: by application scoping and by Postgres row-level security, enabled and forced on every tenant table. The application sets the tenant on each transaction; the application database role is not the table owner and cannot bypass row-level security. pgvector provides embeddings in the same database.

## Options considered
### Shared schema + RLS — chosen
- Pros: Defence in depth; simple operations
- Cons: Must be applied to every table
- Chosen.

### Schema per tenant
- Pros: Strong isolation
- Cons: Migration and operational overhead at scale
- Deferred; possible for enterprise.

### Database per tenant
- Pros: Strongest isolation
- Cons: Operationally heavy
- Deferred; possible for enterprise.

## Consequences
**Positive**
- Isolation survives application bugs

**Negative / costs accepted**
- Every new table needs a policy

**Follow-up work**
- Dedicated-database option for enterprise customers

## Enforcement
- CI script inspects the schema: every table except an explicit allowlist has `tenant_id` and an RLS policy
- Integration test: with tenant A's context, every repository returns nothing for tenant B's data
- Protected path: RLS policies and database roles require human approval

## Guidance for agents
Use the tenant-scoped session; never open a raw connection.

**Do**
```python
async with tenant_session(ctx) as s:  # sets app.tenant_id for the transaction
    ...
```

**Don't**
```python
engine.connect()  # bypasses tenant context
```

## Revisit when
An enterprise customer contractually requires a dedicated database.

## Related
- ADR-001
- ADR-015
