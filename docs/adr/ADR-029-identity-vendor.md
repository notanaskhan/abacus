---
id: ADR-029
title: B2B identity vendor for authentication only
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
Firms require SSO, SCIM and MFA. Client users need simple passwordless login. One person may belong to several firms.

## Decision
Authentication uses WorkOS, subject to a final check of pricing and multi-organisation membership; Clerk is the alternative. The vendor proves identity only. Roles and permissions are never stored in its tokens; the application resolves access from its own database on every request.

## Options considered
### WorkOS — chosen
- Pros: B2B-first: organisations, SSO, SCIM, self-serve admin portal
- Cons: Vendor dependency
- Chosen, pending commercial check.

### Clerk
- Pros: Strong developer experience
- Cons: Enterprise features in higher tiers
- Alternative.

### Auth0
- Pros: Comprehensive
- Cons: Heavier, costlier at scale
- Rejected.

### Self-hosted
- Pros: Control
- Cons: Operating a red-zone system alone
- Rejected.

### AWS Cognito
- Pros: Inside AWS
- Cons: Weak B2B features
- Rejected.

## Consequences
**Positive**
- Enterprise identity features without building them

**Negative / costs accepted**
- A vendor in the login path

**Follow-up work**
- Commercial check; SSO admin portal setup

## Enforcement
- Token claims used only for identity; a lint rule bans reading roles from token claims
- Test: revoking a membership denies the next request with an otherwise valid token

## Guidance for agents
Map vendor identity to a user, then load memberships from the database.

**Do**
```python
user = await identity.resolve_user(token.sub)
ctx = await build_ctx(user, active_tenant)
```

**Don't**
```python
role = token.claims['role']
```

## Revisit when
Pricing, compliance or multi-organisation support fails our needs.

## Related
- ADR-002
- ADR-020
- ADR-030
