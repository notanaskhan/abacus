---
id: ADR-043
title: Rate limiting, fair queuing and resilient pulls
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
Busy season concentrates load on a few providers in a few weeks. Providers enforce rate limits and fail intermittently.

## Decision
Rate limiting per provider and per client company, honouring retry-after signals. Fair queuing across firms. Large reports pulled in date-range chunks. Pulls are resumable and idempotent via checkpoints and idempotency keys of (connection, dataset, period, chunk). A circuit breaker per provider prevents retry storms.

## Options considered
### Full resilience set — chosen
- Pros: Survives busy season and outages
- Cons: Implementation effort
- Chosen.

### Simple retries
- Pros: Easy
- Cons: Retry storms, starvation, duplicates
- Rejected.

## Consequences
**Positive**
- Predictable behaviour under load

**Negative / costs accepted**
- More infrastructure logic

## Enforcement
- Load test with synthetic ledgers at busy-season volumes
- Test: retried chunk produces no duplicate rows
- Fairness test: one tenant's large backlog does not block another's pulls

## Guidance for agents
Pull in idempotent chunks through the limiter.

**Do**
```python
async with limiter.acquire(provider, company_id):
    await pull_chunk(conn, dataset, period, chunk, idem_key=key)
```

**Don't**
```python
for month in months:
    rows += api.get_all(month)  # no limiter, no checkpoint
```

## Revisit when
Provider limits or volumes change materially.

## Related
- ADR-017
- ADR-038
