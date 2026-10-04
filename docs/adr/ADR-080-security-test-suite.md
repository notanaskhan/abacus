---
id: ADR-080
title: Security tests on every pull request
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
Security properties are only real if continuously tested.

## Decision
Every pull request runs: the tenant isolation suite; permission tests generated from the matrix; route introspection; the tenant and row-level security schema check; connector write interception; output control and citation verification tests with seeded violations; and the classification-tag check.

## Options considered
### Continuous security suite — chosen
- Pros: Regressions caught immediately
- Cons: CI time
- Chosen.

## Consequences
**Positive**
- Security regressions cannot merge

**Negative / costs accepted**
- Stage 2 runtime

## Enforcement
- All listed suites are required checks for merge

## Guidance for agents
Add an isolation test for every new repository method.

**Do**
```python
async def test_list_items_other_tenant_returns_nothing(tenant_a, tenant_b): ...
```

**Don't**
```python
# new repository method with no cross-tenant test
```

## Revisit when
Never expected to change.

## Related
- ADR-014
- ADR-027
- ADR-040
- ADR-065
- ADR-066
