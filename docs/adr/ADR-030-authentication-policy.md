---
id: ADR-030
title: Authentication and session policy
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
Firm users handle confidential client data; client users must not face friction that stops them responding to requests.

## Decision
Firm users with an identity provider use SSO; otherwise password or passkey with mandatory MFA. Client users use passwordless email links with optional MFA. Sensitive actions — ethical walls, autonomy policy, exports, legal holds — require fresh MFA. Sessions use short-lived access tokens, rotating refresh tokens, an idle timeout and an absolute limit. Access changes apply on the next request. Users can view and end their sessions.

## Options considered
### Tiered policy — chosen
- Pros: Security where it matters; low friction for clients
- Cons: More policy to implement
- Chosen.

### MFA for everyone including clients
- Pros: Uniform
- Cons: Clients abandon responses
- Rejected.

## Consequences
**Positive**
- Strong protection for firm users and sensitive actions

**Negative / costs accepted**
- Client accounts rely on email security

## Enforcement
- Step-up MFA enforced by `authorise` attribute layer for actions flagged in the matrix
- Session configuration tested; idle and absolute limits asserted

## Guidance for agents
Flag sensitive actions in the matrix; let the attribute layer require MFA.

**Do**
```yaml
export.create:
  conditions:
    mfa_recent: required
```

**Don't**
```yaml
# checking MFA ad hoc inside the export route
```

## Revisit when
Customers require MFA for client users, or a passkey-only policy becomes practical.

## Related
- ADR-027
- ADR-029
