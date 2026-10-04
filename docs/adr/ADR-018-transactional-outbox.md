---
id: ADR-018
title: Transactional outbox and unit of work
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
Every state change must produce an audit event (ADR-007) and often a domain event, even if the process crashes mid-operation.

## Decision
State changes, their audit events and their domain events are written in a single database transaction through a unit-of-work helper. A relay publishes outbox events to Temporal and internal handlers. All consumers are idempotent, deduplicating by event ID.

## Options considered
### Outbox — chosen
- Pros: Atomic; reliable; simple to reason about
- Cons: Relay process to run
- Chosen.

### Publish events directly after commit
- Pros: Simpler
- Cons: Events lost on crash between commit and publish
- Rejected.

## Consequences
**Positive**
- No state change without its audit record
- Reliable cross-module events

**Negative / costs accepted**
- A relay to operate

## Enforcement
- The unit of work raises if a state-changing command commits without an audit event
- Consumers record processed event IDs; duplicate delivery test in CI
- Direct `session.commit()` outside the unit of work is banned by a lint rule

## Guidance for agents
Change state through the unit of work.

**Do**
```python
with uow(ctx) as tx:
    item = tx.requests.mark_received(item_id)
    tx.record('request_item.received', target=item.id)
    tx.emit(RequestItemReceived(item_id=item.id))
```

**Don't**
```python
item.status = 'received'
session.commit()
```

## Revisit when
Never expected to change.

## Related
- ADR-007
- ADR-008
- ADR-017
