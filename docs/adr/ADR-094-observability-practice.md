---
id: ADR-094
title: Observability in practice
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
Standard infrastructure metrics miss the failures that matter most to firms: stale data, expiring connections, agent problems.

## Decision
Standard signals (latency, traffic, errors, saturation) plus domain signals: sync success rate, data freshness per connection, connections expiring soon, queue depth per work class, agent escalation rate, AI cost per hour, cache hit rate, override rate per agent. Four dashboards: platform health, busy-season operations, per-firm health, AI. A synthetic canary firm runs the full flow continuously in production against a provider sandbox. A public status page communicates incidents.

## Options considered
### Domain-aware observability — chosen
- Pros: Catches problems before firms do
- Cons: Instrumentation effort
- Chosen.

## Consequences
**Positive**
- Early detection of domain failures

**Negative / costs accepted**
- More metrics to maintain

**Follow-up work**
- Canary firm setup; status page

## Enforcement
- Every alert links to a runbook
- Canary flow failure pages

## Guidance for agents
Emit domain metrics from services.

**Do**
```python
metrics.gauge('connection.data_freshness_hours', hours, tags={'provider': p})
```

**Don't**
```python
# only CPU and memory monitored
```

## Revisit when
Never expected to change.

## Related
- ADR-022
- ADR-093
- ADR-098
