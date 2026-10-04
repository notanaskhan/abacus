---
id: ADR-044
title: Connector testing strategy
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
Provider APIs change and behave differently from documentation. Tests must catch this before customers do, without using real client data.

## Decision
Connectors are tested with provider sandboxes, recorded responses built only from synthetic data, golden normalisation tests, property tests on normalised data, nightly contract tests against sandboxes, and a synthetic ledger generator for scale.

## Options considered
### Layered connector testing — chosen
- Pros: Catches drift early; safe data
- Cons: Maintenance of fixtures
- Chosen.

### Manual testing against sandbox
- Pros: Easy
- Cons: Drift discovered in production
- Rejected.

## Consequences
**Positive**
- Provider changes detected nightly

**Negative / costs accepted**
- Fixture upkeep

**Follow-up work**
- Synthetic ledger generator

## Enforcement
- CI blocks recordings containing patterns of real identifiers
- Nightly contract job alerts on failure

## Guidance for agents
Use synthetic fixtures.

**Do**
```python
fixture = synthetic.company(accounts=120, months=12, seed=7)
```

**Don't**
```python
# saving a recording from a real client connection
```

## Revisit when
Never expected to change.

## Related
- ADR-038
- ADR-043
