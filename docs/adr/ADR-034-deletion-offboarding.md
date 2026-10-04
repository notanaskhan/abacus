---
id: ADR-034
title: No deletion inside engagements; offboarding by export and crypto-shredding
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
Evidence must be immutable, yet firms leaving the platform and expired retention require reliable deletion — including from write-once storage and backups.

## Decision
Nothing inside an engagement is deleted; errors are corrected by superseding or voiding with a reason. When a firm offboards, it receives a full export (ADR-036); after an agreed grace period its data is deleted using the storage override under dual control, and its per-tenant keys (ADR-035) are destroyed. Personal data requests remove or pseudonymise contact profiles; personal data in retained evidence persists until retention ends, subject to counsel's review per jurisdiction.

## Options considered
### Export + grace + crypto-shredding — chosen
- Pros: Final deletion including backups
- Cons: Dual-control process needed
- Chosen.

### Immediate hard delete
- Pros: Fast
- Cons: Fails retention duties; impossible under Object Lock
- Rejected.

## Consequences
**Positive**
- Deletion is provably final

**Negative / costs accepted**
- Offboarding is a deliberate process

**Follow-up work**
- Offboarding runbook; counsel review of privacy obligations

## Enforcement
- Deletion endpoints for evidence do not exist; voiding requires a reason and writes an audit event
- Offboarding requires two approvers and is logged

## Guidance for agents
Void with a reason; never delete.

**Do**
```python
await evidence_service.void(ctx, version_id, reason='duplicate upload')
```

**Don't**
```python
await session.delete(version)
```

## Revisit when
Never expected to change.

## Related
- ADR-004
- ADR-032
- ADR-035
- ADR-036
