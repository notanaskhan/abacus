---
id: ADR-023
title: Four-layer authorisation model
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
Access decisions combine tenant boundaries, relationships to engagements, roles, and live conditions. Mixing these ad hoc across features produces inconsistent and leaky permissions.

## Decision
Every authorisation decision evaluates four layers in order: (1) tenancy — the active firm; (2) relationships — membership, engagement membership, client access grant, absence of an ethical wall; (3) roles — firm role and engagement role; (4) attributes — engagement state, assignment, expiry, recent MFA. Any layer denying means deny. Deny by default; deny overrides allow.

## Options considered
### Layered model — chosen
- Pros: Consistent, explainable decisions
- Cons: More upfront design
- Chosen.

### Role-only model
- Pros: Simple
- Cons: Cannot express engagement-level access, walls or conditions
- Rejected.

## Consequences
**Positive**
- Every decision is explainable layer by layer

**Negative / costs accepted**
- All four layers must be modelled

**Follow-up work**
- Permission matrix (ADR-027)

## Enforcement
- `authorise` evaluates layers in fixed order; unit tests cover each layer denying independently
- Decision logs record which layer denied

## Guidance for agents
Express access needs as actions; let `authorise` evaluate layers.

**Do**
```python
await authorise(ctx, 'request_item.update', item)
```

**Don't**
```python
if item.engagement.tenant_id == ctx.tenant_id and ctx.role in ('manager', 'senior'): ...
```

## Revisit when
Never expected to change.

## Related
- ADR-020
- ADR-024
- ADR-026
- ADR-027
