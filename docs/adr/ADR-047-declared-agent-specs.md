---
id: ADR-047
title: Every agent is declared in a specification
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
Agents built ad hoc drift in limits, tools and behaviour, and cannot be reviewed or evaluated consistently.

## Decision
Every agent has a specification in `backend/src/agents/specs/` declaring: id, purpose, shape, prompt and version, tier and escalation tier, input and output schemas, tools, limits (tokens, cost, steps, time), autonomy, confidence routing, untrusted inputs and evaluation suite. Code must match its specification.

## Options considered
### Declared specifications — chosen
- Pros: Reviewable, consistent, evaluable
- Cons: Upfront writing
- Chosen.

### Agents defined only in code
- Pros: Faster
- Cons: Limits and tools scattered and inconsistent
- Rejected.

## Consequences
**Positive**
- Every AI capability is visible and governed

**Negative / costs accepted**
- Spec maintenance

## Enforcement
- Schema validation of every spec in CI
- Runtime refuses to start an agent without a valid spec
- Test: every spec references an existing prompt version and evaluation suite

## Guidance for agents
Write the specification before the code.

**Do**
```yaml
id: evidence.screener
shape: workflow
prompt: evidence.screen@v3
limits: {max_cost_usd: 0.03}
```

**Don't**
```yaml
# agent instantiated in code with inline prompt and no limits
```

## Revisit when
Never expected to change.

## Related
- ADR-019
- ADR-046
