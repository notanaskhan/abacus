---
id: ADR-058
title: "Agent hierarchy: engagement agents and specialists"
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
The product's value is continuous, autonomous progress on each engagement, coordinating many capabilities over months.

## Decision
Every engagement has an engagement agent from creation to archive, owning one goal: evidence complete, screened and ready for review by the fieldwork date. It reacts to events, plans, dispatches specialist agents, escalates and reports. Specialists: planner, retriever, screener, matcher, chaser, support finder, change analyst. A portfolio agent across a firm's engagements comes later.

## Options considered
### Orchestrator + specialists — chosen
- Pros: Clear ownership of goals; reliable specialists
- Cons: Orchestrator design effort
- Chosen.

### Flat set of independent agents
- Pros: Simple
- Cons: No one owns the engagement's goal
- Rejected.

## Consequences
**Positive**
- Each engagement is worked continuously

**Negative / costs accepted**
- Orchestrator complexity

**Follow-up work**
- Portfolio agent

## Enforcement
- Engagement creation starts its engagement agent; archive stops it (test)
- Specialists are only invoked by the engagement agent or explicit user action

## Guidance for agents
Route work through the engagement agent.

**Do**
```python
await engagement_agent.signal(eng_id, DocumentReceived(version_id))
```

**Don't**
```python
await screener.run(version_id)  # bypassing the engagement agent from a route
```

## Revisit when
Never expected to change.

## Related
- ADR-046
- ADR-059
- ADR-062
