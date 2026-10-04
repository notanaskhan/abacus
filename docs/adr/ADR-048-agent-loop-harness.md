---
id: ADR-048
title: Agent loop harness on Temporal
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
Agent loops can run away, stall, or end without usable output.

## Decision
Each model call and tool call in a loop is a Temporal activity. Loops end only via `finish` with a schema-valid result or `escalate` with findings and reason. Hard limits on steps, tokens, cost and time stop and escalate. Identical repeated tool calls stop the run. Invalid output gets one repair attempt, then escalation to the next tier, then to a human.

## Options considered
### Durable bounded harness — chosen
- Pros: Safe, recoverable, observable
- Cons: Harness to build
- Chosen.

### Unbounded loop in-process
- Pros: Simple
- Cons: Runaway cost, lost state on crash
- Rejected.

## Consequences
**Positive**
- No silent failures or runaway runs

**Negative / costs accepted**
- Some valid runs stop early and escalate

## Enforcement
- Harness unit tests for each limit and stopping rule
- Loops cannot return without `finish` or `escalate` (enforced by harness types)

## Guidance for agents
End loops explicitly.

**Do**
```python
return await tools.finish(SupportMatchResult(...))
```

**Don't**
```python
return 'I found the invoice, looks fine'
```

## Revisit when
Never expected to change.

## Related
- ADR-017
- ADR-047
