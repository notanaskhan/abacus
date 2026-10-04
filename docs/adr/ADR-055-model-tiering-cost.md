---
id: ADR-055
title: Model tiers, cascades, caching, batching and reuse
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
Model cost is the largest variable cost in the product and determines margin.

## Decision
Tasks are assigned small, medium or large tiers. Cascades start small and escalate on low confidence or invalid output. Prompt caching is exploited through context order. Non-urgent bulk work uses batch processing. Identical inputs reuse prior results.

## Options considered
### Full cost toolkit — chosen
- Pros: Healthy margins at scale
- Cons: Routing logic
- Chosen.

### Single large model
- Pros: Simple
- Cons: Margins collapse
- Rejected.

## Consequences
**Positive**
- Cost per engagement controlled

**Negative / costs accepted**
- Routing and cache logic

**Follow-up work**
- Detailed cost controls in topic 6

## Enforcement
- Specs declare tier and escalation tier
- Gateway metrics report cost per agent per engagement

## Guidance for agents
Declare tiers; let the gateway route.

**Do**
```yaml
tier: small
escalation_tier: medium
```

**Don't**
```yaml
model: largest-available  # hard-coded in module
```

## Revisit when
Model pricing or capability changes materially.

## Related
- ADR-019
- ADR-051
