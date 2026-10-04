---
id: ADR-007
title: Append-only audit trail in a separate event log
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
The audit trail is what customers ultimately buy and what inspectors examine. It must be complete, unalterable, and independent of the domain tables it describes.

## Decision
All state changes write an `AuditEvent` to an insert-only table in the same transaction as the change (ADR-018). Each event records actor (human, agent or system), action, target, a reference to before and after state, trace ID and timestamp. Tamper evidence — each event carrying a fingerprint of the previous event per tenant — is added in a later version.

## Options considered
### Separate append-only log — chosen
- Pros: Independent, complete, queryable
- Cons: Extra writes on every change
- Chosen.

### Change-history columns on each table
- Pros: Less infrastructure
- Cons: Incomplete, easy to bypass, mixed with domain data
- Rejected.

## Consequences
**Positive**
- A single complete record of every action

**Negative / costs accepted**
- Write volume grows with activity

**Follow-up work**
- Per-tenant hash chaining

## Enforcement
- Application role has INSERT only on `audit_events`
- The unit-of-work helper refuses to commit a state-changing command without at least one audit event (ADR-018)
- Test: every service command in the registry writes an audit event

## Guidance for agents
Record audit events through the unit of work, never directly.

**Do**
```python
with uow(ctx) as tx:
    tx.record('evidence.version_added', target=v.id, after=v.ref)
```

**Don't**
```python
session.add(AuditEvent(...)); session.commit()  # outside the unit of work
```

## Revisit when
Tamper evidence is implemented, or an external timestamping service is required by a customer.

## Related
- ADR-004
- ADR-018
