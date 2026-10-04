---
id: ADR-092
title: Reduced-risk change policy from January to March
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
Failures during busy season do the greatest damage to firms and reputation.

## Decision
From January to March: only fixes and already-flagged features; no schema changes during working hours; no model or prompt upgrades without full evaluation and shadow run; every production deploy has a written rollback plan. Major changes ship October to December.

## Options considered
### Seasonal policy — chosen
- Pros: Stability when it matters most
- Cons: Slower delivery in Q1
- Chosen.

## Consequences
**Positive**
- Stability during peak

**Negative / costs accepted**
- Feature velocity reduced in Q1

## Enforcement
- Deploy pipeline requires a rollback-plan field during the policy window

## Guidance for agents
Ship large changes in Q4.

**Do**
```python
# Q1 deploy: fix only, rollback plan attached
```

**Don't**
```python
# new schema migration at 10am on a February Monday
```

## Revisit when
Never expected to change.

## Related
- ADR-075
- ADR-089
