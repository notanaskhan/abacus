---
id: ADR-070
title: Cost attribution, cost regression gates and a cost ceiling
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
Gross margin per customer must be known from day one, and prompt changes can quietly raise cost.

## Decision
Every model call is attributed to firm, engagement, agent and prompt version. Evaluation runs record cost per case; CI fails if cost per case rises beyond an agreed threshold without approval. Target AI cost is at most roughly 10% of the engagement price, and agent cost limits derive from a maintained cost model.

## Options considered
### Attribution and gates — chosen
- Pros: Margin visibility; no silent creep
- Cons: Metering work
- Chosen.

## Consequences
**Positive**
- Margin per customer is measurable

**Negative / costs accepted**
- Cost model upkeep

**Follow-up work**
- Cost model document

## Enforcement
- Gateway writes a usage record per call with required attribution fields
- Eval CI job compares cost per case with the baseline

## Guidance for agents
Attribute every call.

**Do**
```python
await ai.run(ctx, ..., agent='evidence.screener')  # ctx carries firm and engagement
```

**Don't**
```python
# model call without engagement attribution
```

## Revisit when
Pricing model changes.

## Related
- ADR-019
- ADR-069
