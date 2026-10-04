---
id: ADR-062
title: Engagement agents as long-lived Temporal workflows
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
Engagement agents live for months, react to events, sleep on timers, and must survive deployments and failures.

## Decision
Each engagement agent is a Temporal workflow from engagement creation to archive. Domain events arrive as signals via the outbox. Timers schedule planning and follow-ups. Long runs periodically restart with state carried forward to bound history size. Specialists run as child workflows with their own limits. Pause switches exist per engagement and per firm; pausing preserves state.

## Options considered
### Long-lived workflows — chosen
- Pros: Durable months-long agents
- Cons: Workflow versioning discipline
- Chosen.

### Cron jobs and stateless handlers
- Pros: Simple
- Cons: State scattered; no durable agent
- Rejected.

## Consequences
**Positive**
- Months-long agents are practical and safe

**Negative / costs accepted**
- Versioning of long-running workflow code

## Enforcement
- Replay tests in CI (ADR-017)
- Test: pause and resume preserves state and pending actions
- History size alarms trigger state carry-forward

## Guidance for agents
Signal the engagement agent; never mutate its state externally.

**Do**
```python
await client.get_workflow_handle(f'engagement-agent-{eng_id}').signal('event', evt)
```

**Don't**
```python
db.execute('UPDATE agent_state SET ...')
```

## Revisit when
Never expected to change.

## Related
- ADR-017
- ADR-018
- ADR-058
