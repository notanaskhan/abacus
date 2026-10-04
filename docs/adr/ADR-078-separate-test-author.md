---
id: ADR-078
title: Separate test author for amber and red work
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
Agents that write both code and tests tend to encode their bugs into the tests.

## Decision
For amber and red tasks, tests are written from the spec's acceptance criteria in a separate session before or independently of the implementation; the implementation session must make them pass without editing them except with approval.

## Options considered
### Separate sessions — chosen
- Pros: Tests reflect the spec, not the code
- Cons: Two sessions per task
- Chosen.

### Same session writes both
- Pros: Faster
- Cons: Tests mirror bugs
- Rejected for amber and red.

## Consequences
**Positive**
- Tests act as an independent specification

**Negative / costs accepted**
- More orchestration per task

## Enforcement
- Task template records test session and implementation session
- Test files changed in the implementation PR are flagged for reviewer attention

## Guidance for agents
Write tests from acceptance criteria first.

**Do**
```python
def test_ac3_rejects_wrong_period(): ...  # written from SPEC-012 AC-3
```

**Don't**
```python
# tests adjusted to match the implementation's output
```

## Revisit when
Never expected to change.

## Related
- ADR-079
