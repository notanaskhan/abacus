---
id: ADR-073
title: Two access routes to the same model family
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
Provider outages must not stop the product. Switching to a different model family changes outputs and invalidates evaluations.

## Decision
Models are accessible through two routes to the same model family — directly from the provider and through a major cloud platform within our AWS trust boundary — after verifying parity of required features such as prompt caching and batch processing. Failover to a different model family is permitted only for agents whose evaluation suite passes on it.

## Options considered
### Same model, two routes — chosen
- Pros: Continuity without behaviour change
- Cons: Two integrations
- Chosen.

### Failover to another provider's model
- Pros: Broad continuity
- Cons: Unvalidated behaviour
- Allowed only per agent with passing evals.

## Consequences
**Positive**
- Outage resilience with evaluated behaviour

**Negative / costs accepted**
- Feature parity to verify

## Enforcement
- Gateway route configuration per agent lists allowed routes and models
- Eval suite run per allowed route/model

## Guidance for agents
Configure allowed routes per agent.

**Do**
```yaml
routes: [direct, cloud]
fallback_models: []   # none validated yet
```

**Don't**
```yaml
fallback_models: [any-other-model]
```

## Revisit when
A route loses feature parity or a validated alternative model emerges.

## Related
- ADR-021
- ADR-072
- ADR-074
