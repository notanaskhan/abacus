---
id: ADR-033
title: Legal hold on engagements and clients
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
Litigation or regulatory inquiry can require preserving data beyond normal retention.

## Decision
Firm admins can place a legal hold on an engagement or a client. A hold suspends all deletion, including at the storage layer via S3 legal hold. Placing or lifting a hold requires fresh MFA and is audited.

## Options considered
### Legal hold — chosen
- Pros: Meets preservation duties
- Cons: Holds must be reviewed
- Chosen.

## Consequences
**Positive**
- Preservation duties can be met on demand

**Negative / costs accepted**
- Held data persists until released

## Enforcement
- Deletion process checks for holds and refuses held data
- Test: held engagement survives retention expiry

## Guidance for agents
Check holds through the retention service.

**Do**
```python
if await retention.is_held(engagement): return
```

**Don't**
```python
delete_engagement_files(engagement)  # ignoring holds
```

## Revisit when
Never expected to change.

## Related
- ADR-032
- ADR-034
