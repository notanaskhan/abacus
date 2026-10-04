---
id: ADR-074
title: Pinned models and prompts with gated upgrades
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
Provider model updates and prompt edits change behaviour. Providers also retire models.

## Decision
Exact model versions are pinned. Model and prompt upgrades must pass the evaluation suite, then run in shadow mode on real traffic with outputs compared, then roll out in stages by firm. Provider retirement dates are tracked with migration plans.

## Options considered
### Gated lifecycle — chosen
- Pros: No surprise behaviour changes
- Cons: Slower upgrades
- Chosen.

### Use latest model aliases
- Pros: Effortless
- Cons: Silent behaviour drift
- Rejected.

## Consequences
**Positive**
- Behaviour changes only deliberately

**Negative / costs accepted**
- Upgrade process overhead

**Follow-up work**
- Model retirement calendar

## Enforcement
- Lint rejects model aliases without explicit versions
- Rollout flags per firm for model and prompt versions

## Guidance for agents
Pin exact versions in configuration.

**Do**
```yaml
model: <provider-model-id-with-date>
```

**Don't**
```yaml
model: latest
```

## Revisit when
Never expected to change.

## Related
- ADR-019
- ADR-073
