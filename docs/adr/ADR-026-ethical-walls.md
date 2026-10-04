---
id: ADR-026
title: Ethical walls override every role
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
Firms must be able to exclude specific people from specific clients to manage conflicts. A wall that any role can bypass is not a wall.

## Decision
An ethical wall excludes a user from a client and all its engagements, present and future. Walls override every role, including firm admin, practice leader and quality partner. Creating or removing a wall requires firm admin, fresh MFA, and is audited. Walls take effect on the next request; sessions and cached permissions are invalidated. Independence-conflict rules between engagement types arrive with the CAS product as a firm-configurable policy.

## Options considered
### Absolute walls — chosen
- Pros: Trustworthy conflict management
- Cons: Occasionally inconvenient
- Chosen.

### Walls overridable by admins
- Pros: Convenient
- Cons: Defeats the purpose
- Rejected.

## Consequences
**Positive**
- Conflicts are enforced structurally

**Negative / costs accepted**
- Admins cannot see walled clients even for administration

**Follow-up work**
- Independence rules for CAS

## Enforcement
- Layer 2 of `authorise` checks walls before roles
- `visible()` filters exclude walled clients from every list
- Test matrix: every role is denied on a walled client, including firm admin

## Guidance for agents
Let `authorise` and `visible` handle walls; never special-case them.

**Do**
```python
query = query.where(visible(ctx, Engagement))
```

**Don't**
```python
if ctx.is_admin: return all_engagements
```

## Revisit when
Never expected to change.

## Related
- ADR-023
- ADR-024
