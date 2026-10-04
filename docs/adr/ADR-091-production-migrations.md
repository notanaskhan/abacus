---
id: ADR-091
title: Safe production migrations
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
Migrations on live data cause lock-ups, data loss and failed deploys.

## Decision
Migrations run as a separate pre-deploy step, never at application startup. Destructive changes use expand-then-contract across multiple deploys. Migration sessions set lock and statement timeouts. Large backfills run as throttled, resumable Temporal workflows. Every migration is rehearsed in staging against production-sized synthetic data.

## Options considered
### Disciplined migrations — chosen
- Pros: No migration outages
- Cons: Slower schema evolution
- Chosen.

## Consequences
**Positive**
- Schema changes without downtime

**Negative / costs accepted**
- Multi-deploy changes

## Enforcement
- Migration linter (ADR-015) and timeout settings enforced by the migration runner
- Deploy pipeline runs migrations as a distinct job

## Guidance for agents
Backfill through a workflow.

**Do**
```python
await client.start_workflow(BackfillFulfilmentConfirmedBy.run, ...)
```

**Don't**
```python
op.execute('UPDATE fulfilments SET confirmed_by = ...')  # whole table in one migration
```

## Revisit when
Never expected to change.

## Related
- ADR-015
- ADR-017
