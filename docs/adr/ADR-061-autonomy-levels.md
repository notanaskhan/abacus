---
id: ADR-061
title: Four autonomy levels; decisions remain human
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
Firms will extend trust to agents gradually and need control over how much the agent does unprompted.

## Decision
Autonomy is set per firm, optionally per engagement: Level 0 advise; Level 1 routine (re-pull, screen, propose matches, routine reminders); Level 2 manage (own daily plan, sequence chasing, escalate to team); Level 3 portfolio (coordinate across engagements). At every level, decisions remain human (ADR-005).

## Options considered
### Graduated levels — chosen
- Pros: Matches how trust is earned
- Cons: Configuration surface
- Chosen.

### Fixed autonomy
- Pros: Simple
- Cons: Too much for some firms, too little for others
- Rejected.

## Consequences
**Positive**
- Firms control agent freedom

**Negative / costs accepted**
- More configurations to test

## Enforcement
- Autonomy level is part of the permission evaluation for agent actions
- Test matrix covers each action at each level

## Guidance for agents
Check the level through the autonomy service.

**Do**
```python
await autonomy.allows(ctx, Action.SEND_REMINDER)
```

**Don't**
```python
if firm.ai_enabled: send_reminder()
```

## Revisit when
Never expected to change.

## Related
- ADR-005
- ADR-027
- ADR-060
