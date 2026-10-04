---
id: ADR-063
title: Agency is visible
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
Users trust and value agents they can see working. Invisible automation feels like nothing happened.

## Decision
Every engagement has an activity feed showing what the agent did and why, linked to the records it touched. Managers receive a daily briefing on readiness, risks and overnight activity. After the MVP, a natural-language command bar lets managers direct the agent; it is a control surface over the engagement agent, not a free-form chatbot.

## Options considered
### Visible agency — chosen
- Pros: Trust, adoption, demo value
- Cons: UI work
- Chosen.

## Consequences
**Positive**
- The agent's value is obvious to users

**Negative / costs accepted**
- Feed and briefing to build

**Follow-up work**
- Command bar after MVP

## Enforcement
- Every engagement agent action writes an activity entry with rationale and links
- Command bar inputs are converted to planned actions validated like any other

## Guidance for agents
Write an activity entry for every agent action.

**Do**
```python
activity.record(ctx, eng_id, kind='reminder_sent', rationale=r, links=[item_id])
```

**Don't**
```python
send_reminder(item)  # no visible trace for users
```

## Revisit when
Never expected to change.

## Related
- ADR-054
- ADR-058
- ADR-060
