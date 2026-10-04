---
id: ADR-060
title: Hybrid decision-making for the engagement agent
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
The engagement agent must be both predictable for routine events and intelligent about priorities.

## Decision
Routine events trigger deterministic policies. A daily LLM planning step, and planning on unusual events, receives code-computed engagement state and proposes a prioritised plan with reasons. Every proposed action is validated against the autonomy policy and permission matrix; allowed actions run, others queue for approval.

## Options considered
### Hybrid — chosen
- Pros: Reliable routine, intelligent prioritisation
- Cons: Two decision paths
- Chosen.

### LLM decides everything
- Pros: Flexible
- Cons: Costly and unpredictable for routine events
- Rejected.

### Rules only
- Pros: Predictable
- Cons: No judgement on priorities
- Rejected.

## Consequences
**Positive**
- Predictable baseline with intelligent planning on top

**Negative / costs accepted**
- Policy and planner both to maintain

**Follow-up work**
- LLM planner before fieldwork

## Enforcement
- Policies are declarative and unit-tested
- Planner output schema lists actions; every action passes `authorise` and autonomy checks before execution

## Guidance for agents
Validate every planned action.

**Do**
```python
for action in plan.actions:
    if await autonomy.allows(ctx, action): await execute(action)
    else: await approvals.queue(ctx, action)
```

**Don't**
```python
for action in plan.actions: await execute(action)
```

## Revisit when
Never expected to change.

## Related
- ADR-027
- ADR-058
- ADR-061
