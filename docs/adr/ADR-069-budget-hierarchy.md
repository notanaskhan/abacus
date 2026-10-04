---
id: ADR-069
title: Budget hierarchy and denial-of-wallet controls
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
Per-engagement pricing fixes revenue per engagement, so AI cost must be bounded at every level. Loops, bugs and oversized inputs can drive runaway cost.

## Decision
Budgets apply per call, per agent run, per engagement, per firm per month, and platform-wide per day. Soft limits alert and degrade (cheaper tiers, deferral of background work); hard limits allow only essential work. Every agent declares itself essential or deferrable. Upload size and page limits, per-engagement action caps and cost anomaly alerts prevent denial of wallet.

## Options considered
### Hierarchical budgets — chosen
- Pros: Predictable cost; graceful degradation
- Cons: Budget configuration
- Chosen.

### Monthly invoice review
- Pros: Simple
- Cons: Runaway cost found too late
- Rejected.

## Consequences
**Positive**
- Cost bounded at every level

**Negative / costs accepted**
- Some work deferred under pressure

## Enforcement
- Gateway enforces every level before calling providers
- Specs declare `work_class: essential | deferrable`
- Anomaly job alerts when an engagement exceeds a multiple of its normal spend rate

## Guidance for agents
Declare work class and limits in the spec.

**Do**
```yaml
work_class: deferrable
limits: {max_cost_usd: 0.02}
```

**Don't**
```yaml
# agent with no limits or work class
```

## Revisit when
Pricing or cost structure changes.

## Related
- ADR-019
- ADR-070
