---
id: ADR-020
title: Bought authentication, in-house authorisation
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
Firms will require SSO and MFA. Authentication is a red-zone problem best bought. Authorisation encodes our domain (engagements, ethical walls, client access) and must be ours.

## Decision
Authentication uses a B2B identity provider supporting organisations, SSO, SCIM and MFA (vendor chosen in topic 3). Authorisation lives in a single `authorise(actor, action, resource)` interface in the identity module; no permission logic exists anywhere else.

## Options considered
### Buy authN, own authZ — chosen
- Pros: Enterprise-ready login; domain-accurate permissions
- Cons: Vendor dependency for login
- Chosen.

### Build both
- Pros: Full control
- Cons: High risk; slow
- Rejected.

### Buy both
- Pros: Fast
- Cons: Generic models fit our domain poorly
- Rejected.

## Consequences
**Positive**
- Enterprise identity features without building them

**Negative / costs accepted**
- A login vendor in the trust chain

**Follow-up work**
- Authorisation model design (topic 3)

## Enforcement
- Route introspection test: every route uses the auth context
- Lint rule bans role or permission checks outside the identity module's `authorise`
- Protected path: authorisation module changes require human review

## Guidance for agents
Ask the authorisation interface.

**Do**
```python
await authorise(ctx, 'evidence.accept', version)
```

**Don't**
```python
if ctx.user.role == 'manager':  # permission logic outside authorise
```

## Revisit when
Customers require on-premises identity or a vendor fails to meet compliance needs.

## Related
- ADR-002
- ADR-012
