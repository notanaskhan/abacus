---
id: ADR-002
title: Global user identity with per-firm memberships
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
Client controllers often work with several firms (audit, tax, advisory), and some professionals move between firms. Requiring separate logins per firm is poor UX; deriving access from identity alone is unsafe.

## Decision
A `User` is a single global identity with one login. All data access comes from a `Membership` (firm staff) or an engagement-scoped client access grant. Every request operates within exactly one active tenant; a user's access is always evaluated in that tenant's context.

## Options considered
### Global identity + memberships — chosen
- Pros: One login; clean separation of who you are from what you can see
- Cons: Requires an explicit active-tenant context on every request
- Chosen.

### Separate user per firm
- Pros: Simplest isolation
- Cons: Multiple logins for the same person; poor client experience
- Rejected.

## Consequences
**Positive**
- One login per human across all firms
- Access revocation is per membership, not per account

**Negative / costs accepted**
- Every request must carry and validate an active tenant

**Follow-up work**
- Tenant switcher in the UI for users with several memberships

## Enforcement
- The request context resolves `tenant_id` from a validated membership, never from the user record or a client-supplied value alone
- Test: a user with memberships in two firms sees only the active firm's data per request
- Route introspection test confirms every route depends on the auth context (ADR-012)

## Guidance for agents
Tenant comes from the authenticated membership in the request context.

**Do**
```python
tenant_id = ctx.membership.tenant_id
```

**Don't**
```python
tenant_id = request.headers['X-Tenant-Id']  # trusting the client
```

## Revisit when
Firms request delegated cross-firm access, such as an outsourced reviewer working across several firms.

## Related
- ADR-001
- ADR-020
