---
id: ADR-079
title: Coverage floors, mutation testing and test hygiene
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
Coverage alone can be satisfied by tests that execute code without asserting behaviour — a common pattern in AI-written tests.

## Decision
Coverage floors apply everywhere, higher on red-zone modules. Mutation testing runs on red-zone modules (authorisation, tenancy, evidence, audit trail, AI gateway) with a minimum mutation score. Thresholds are in a protected file. Skips and expected failures require a linked issue. Test deletion requires approval. Flaky tests are quarantined with an owner and a deadline.

## Options considered
### Coverage plus mutation — chosen
- Pros: Tests proven to catch bugs
- Cons: Slower nightly runs
- Chosen.

### Coverage only
- Pros: Simple
- Cons: Gameable
- Rejected.

## Consequences
**Positive**
- Tests on critical code are proven meaningful

**Negative / costs accepted**
- Mutation runs are slow (nightly)

## Enforcement
- Protected path for threshold configuration
- Lint rejects `skip`/`xfail` without an issue reference

## Guidance for agents
Reference an issue for any skip.

**Do**
```python
@pytest.mark.skip(reason='ISSUE-88: provider sandbox outage')
```

**Don't**
```python
@pytest.mark.skip
```

## Revisit when
Never expected to change.

## Related
- ADR-078
- ADR-083
