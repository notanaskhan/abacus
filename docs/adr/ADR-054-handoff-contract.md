---
id: ADR-054
title: Standard human handoff contract
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
Reviewers must verify agent work quickly, and their feedback must improve the system.

## Decision
Every agent output presents: proposed action, confidence, short rationale, citations to exact sources, and what could not be verified. Reviewers accept, edit or reject; rejections require a reason code. Reason-coded feedback creates firm examples, candidate firm rules and evaluation cases.

## Options considered
### Standard contract — chosen
- Pros: Fast review; learning loop fuel
- Cons: Discipline in every agent
- Chosen.

## Consequences
**Positive**
- Reviews take seconds
- The system improves per firm

**Negative / costs accepted**
- Every output needs citations

## Enforcement
- Output schemas extend a common `Handoff` base
- Reject action requires a reason code from the catalogue

## Guidance for agents
Return the handoff structure.

**Do**
```python
class ScreeningOutput(Handoff):
    action: Literal['ready_for_review','needs_revision']
```

**Don't**
```python
return {'result': 'looks good'}
```

## Revisit when
Never expected to change.

## Related
- ADR-005
- ADR-053
