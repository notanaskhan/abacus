---
id: ADR-040
title: Read-only access enforced by the platform
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
Some providers offer no read-only scope; QuickBooks Online's accounting scope grants read and write. Clients and IT reviewers need an honest and verifiable guarantee.

## Decision
Connector clients implement read operations only; no write methods exist. Worker outbound traffic is restricted to approved provider hosts. A test fails if any connector issues a non-read request. Every pull is recorded in the client-visible access log. Consent copy states that the platform is technically restricted to reading and logs every access; it never claims the provider token itself is read-only where it isn't. Where providers support read-only scopes or roles, those are requested.

## Options considered
### Platform-enforced read-only — chosen
- Pros: Honest, verifiable guarantee
- Cons: Must be maintained in code and network policy
- Chosen.

### Rely on provider scopes
- Pros: No extra work
- Cons: Not available on every provider
- Rejected.

## Consequences
**Positive**
- A defensible answer for IT and security review

**Negative / costs accepted**
- Ongoing enforcement

**Follow-up work**
- Consent copy reviewed per provider

## Enforcement
- Static check: connector HTTP clients expose only GET (and provider-specific read POSTs explicitly allowlisted)
- Network egress allowlist enforced in infrastructure
- Integration test intercepts traffic and fails on any write

## Guidance for agents
Use the read-only client.

**Do**
```python
resp = await qbo.read('reports/TrialBalance', params)
```

**Don't**
```python
await http.post(f'{base}/journalentry', json=entry)
```

## Revisit when
Write access arrives with the CAS product, under a separate ADR and connection scope.

## Related
- ADR-021
- ADR-037
