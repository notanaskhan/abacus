---
id: ADR-072
title: Admission control and graceful degradation
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
Provider rate limits are hard ceilings. Exceeding them causes retry storms; silent failures erode trust.

## Decision
The gateway tracks provider capacity globally and admits work by priority, never exceeding provider limits. Under constraint it steps down: defer batch, defer background, move eligible agents to cheaper tiers where evaluations allow, then queue with visible status. Nothing fails silently.

## Options considered
### Admission control — chosen
- Pros: Stable under pressure; transparent
- Cons: Capacity tracking logic
- Chosen.

### Retry on rate-limit errors
- Pros: Simple
- Cons: Retry storms
- Rejected.

## Consequences
**Positive**
- Predictable behaviour at capacity

**Negative / costs accepted**
- Some work delayed

## Enforcement
- Gateway token-bucket per provider and model
- Every queued item exposes a user-visible status and estimate

## Guidance for agents
Request admission through the gateway.

**Do**
```python
async with gateway.admit(ctx, spec): ...
```

**Don't**
```python
while True:
    try: return call()
    except RateLimit: time.sleep(1)
```

## Revisit when
Never expected to change.

## Related
- ADR-071
- ADR-073
