---
id: ADR-085
title: Synthetic test data; no real client data in the repository
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
Tests and evaluations need realistic data, but client data in a repository is a breach waiting to happen.

## Decision
A seeded synthetic company generator produces ledgers, bank statements, invoices, contracts and request lists, including flawed documents for every failure-taxonomy category and adversarial documents. The same seed always produces the same company. Real client data never enters the repository; a commit scan blocks patterns resembling real identifiers.

## Options considered
### Synthetic generator — chosen
- Pros: Realistic, safe, reproducible
- Cons: Generator to build
- Chosen.

## Consequences
**Positive**
- Safe, reproducible test data

**Negative / costs accepted**
- Generator maintenance

**Follow-up work**
- Generator implementation

## Enforcement
- Pre-commit and CI scans for identifier patterns
- Fixtures must reference a generator seed

## Guidance for agents
Generate fixtures from seeds.

**Do**
```python
company = synthetic.company(seed=42, entities=1, months=12, flaws=['wrong_period'])
```

**Don't**
```python
# fixture copied from a design partner's export
```

## Revisit when
Never expected to change.

## Related
- ADR-044
- ADR-081
