---
id: ADR-059
title: Agents coordinate through shared state and events
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
Agent-to-agent conversation is fragile, hard to test and impossible to audit.

## Decision
Agents never converse with each other. Specialists write typed results to the domain model — screening results, proposed fulfilments, drafts — and announce them via domain events. The engagement agent reads state and decides next steps. Every handoff is a typed record in the audit trail.

## Options considered
### Shared state — chosen
- Pros: Auditable, testable handoffs
- Cons: Less free-form
- Chosen.

### Agent conversation
- Pros: Flexible in demos
- Cons: Fragile; unauditable
- Rejected.

## Consequences
**Positive**
- Every inter-agent handoff is auditable

**Negative / costs accepted**
- Typed results needed for each specialist

## Enforcement
- Specialists have no tool or API to message other agents
- Specialist outputs persist through services that write audit events

## Guidance for agents
Write results to state and emit events.

**Do**
```python
with uow(ctx) as tx:
    tx.screening.save(result)
    tx.emit(ScreeningCompleted(version_id=v))
```

**Don't**
```python
await chaser_agent.send_message('screener says doc is bad, please chase')
```

## Revisit when
Never expected to change.

## Related
- ADR-018
- ADR-058
