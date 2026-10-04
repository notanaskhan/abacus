---
id: ADR-057
title: Temporal is the only orchestrator; no agent framework for now
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
Agent frameworks duplicate durable orchestration, add abstraction that hides model inputs, and change APIs quickly — producing mixed-version code when AI writes it.

## Decision
Temporal is the only durable orchestrator. Inner agent loops are hand-rolled inside `ai_gateway` in the MVP. When trigger conditions are met — three or more loop agents, a complex reasoning graph, or team expertise — Pydantic AI or LangGraph may be adopted for inner reasoning only, running inside Temporal activities, confined to `ai_gateway`, with pinned versions and a reference document.

## Options considered
### Hand-rolled inner loops now — chosen
- Pros: Full control; no churn
- Cons: We maintain the loop
- Chosen.

### LangGraph as orchestrator
- Pros: Graph semantics; ecosystem
- Cons: Duplicates Temporal; two sources of state
- Rejected.

### Pydantic AI for inner loops
- Pros: Typed; Temporal-compatible
- Cons: Not needed for one loop
- Deferred until triggers are met.

## Consequences
**Positive**
- One source of truth for agent state

**Negative / costs accepted**
- Loop code to maintain

## Enforcement
- import-linter forbids agent framework imports outside `ai_gateway`
- Dependency allowlist excludes agent frameworks until an ADR approves one

## Guidance for agents
Build loops with the internal harness.

**Do**
```python
result = await harness.run_loop(spec='sampling.support_finder', ctx=ctx, inputs=...)
```

**Don't**
```python
from langgraph.graph import StateGraph  # in a module
```

## Revisit when
Trigger conditions in the decision are met.

## Related
- ADR-017
- ADR-019
- ADR-048
