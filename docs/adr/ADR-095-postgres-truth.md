---
id: ADR-095
title: Postgres holds the truth; agents are rebuildable
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
If orchestration history were lost, engagements must continue without losing data or progress.

## Decision
All business truth lives in Postgres: request items, evidence, decisions, events. Temporal holds orchestration state only. Every engagement agent can rebuild its working state from the database and resume.

## Options considered
### Rebuildable agents — chosen
- Pros: Temporal never the sole copy of anything important
- Cons: Rebuild logic required
- Chosen.

## Consequences
**Positive**
- Simpler disaster recovery

**Negative / costs accepted**
- Rebuild path must be maintained and tested

## Enforcement
- Test: terminate an engagement agent, start fresh, assert it reconstructs pending work from the database
- No business data stored only in workflow state

## Guidance for agents
Derive agent state from the database on start.

**Do**
```python
state = await EngagementState.load(ctx, engagement_id)
```

**Don't**
```python
self.pending_items = signal_payloads  # only source of truth
```

## Revisit when
Never expected to change.

## Related
- ADR-018
- ADR-062
- ADR-096
