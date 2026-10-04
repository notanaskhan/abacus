---
id: ADR-006
title: Model client entities from day one
status: accepted
date: 2026-10-04
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Many clients are groups of legal entities. The MVP supports one entity, but retrofitting entity scoping later would touch every table.

## Decision
A `Client` has one or more `ClientEntity` records. Connections, ledger data and evidence provenance are always entity-scoped. Engagements reference one or more entities. The MVP interface exposes a single entity.

## Options considered
### Entity-scoped from day one — chosen
- Pros: No rebuild for group audits
- Cons: Slight extra complexity now
- Chosen.

### Client-level only
- Pros: Simpler MVP
- Cons: Rebuild when the first group audit arrives
- Rejected.

## Consequences
**Positive**
- Consolidations and group audits need no remodel

**Negative / costs accepted**
- One more key on several tables

## Enforcement
- `entity_id` is NOT NULL on `connections`, ledger tables and provenance records
- Test: two entities under one client keep separate ledger data

## Guidance for agents
Always scope ledger and connection operations by entity.

**Do**
```python
ledger_service.trial_balance(ctx, entity_id, period)
```

**Don't**
```python
ledger_service.trial_balance(ctx, client_id, period)
```

## Revisit when
Never expected to change.

## Related
- ADR-001
