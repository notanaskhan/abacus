---
id: ADR-071
title: Work classes and fair concurrency
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
Busy season concentrates load. Background work must never delay a user waiting on a result, and one firm must not starve others.

## Decision
Four work classes — interactive, time-sensitive, background, batch — run on separate Temporal task queues with separate worker pools. Per-firm and per-engagement concurrency caps with fair queuing apply across classes.

## Options considered
### Classed queues with fairness — chosen
- Pros: Responsive under load; fair
- Cons: More queues to operate
- Chosen.

### Single queue
- Pros: Simple
- Cons: Users wait behind bulk work; starvation
- Rejected.

## Consequences
**Positive**
- Interactive latency protected

**Negative / costs accepted**
- Worker pool tuning

## Enforcement
- Specs declare work class; dispatch uses the matching queue
- Load test asserts interactive latency under peak background load

## Guidance for agents
Dispatch to the declared queue.

**Do**
```python
await dispatch(spec, ctx, inputs)  # routes by spec.work_class
```

**Don't**
```python
await client.start_workflow(..., task_queue='default')
```

## Revisit when
Never expected to change.

## Related
- ADR-017
- ADR-069
