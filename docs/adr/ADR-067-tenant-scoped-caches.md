---
id: ADR-067
title: Caches and examples never cross firms
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
Result reuse, prompt caching and example retrieval are efficient, but any sharing across firms leaks information.

## Decision
Prompt caching keys, result reuse and few-shot example retrieval are scoped to a single firm. Identical inputs from different firms always produce separate runs.

## Options considered
### Firm-scoped caching — chosen
- Pros: Zero cross-firm leakage
- Cons: Some duplicated cost
- Chosen.

### Global result cache
- Pros: Lower cost
- Cons: Cross-firm leakage
- Rejected.

## Consequences
**Positive**
- No information flows between firms through AI infrastructure

**Negative / costs accepted**
- Slightly higher cost

## Enforcement
- Cache keys include `tenant_id` by construction in the gateway
- Test: identical input in two tenants yields two model calls

## Guidance for agents
Use the gateway's cache API, which scopes by tenant.

**Do**
```python
await ai.cached_run(ctx, ...)
```

**Don't**
```python
cache.get(sha256(input))  # global key
```

## Revisit when
Never expected to change.

## Related
- ADR-053
- ADR-055
