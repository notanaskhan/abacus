---
id: ADR-082
title: Evaluation cadence and production drift monitoring
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
Agent quality can degrade through code changes, prompt changes, model changes or shifts in real-world inputs.

## Decision
A fast evaluation subset runs on pull requests touching prompts, specs, tools, context builders or the gateway. The full suite runs nightly and before every model or prompt rollout. In production, acceptance and override rates per agent are monitored; rising override rates raise drift alerts.

## Options considered
### Continuous evaluation — chosen
- Pros: Degradation caught early
- Cons: Evaluation cost
- Chosen.

## Consequences
**Positive**
- Drift is detected from real use

**Negative / costs accepted**
- Recurring model spend for evaluations

## Enforcement
- CI path filters trigger the subset
- Override-rate dashboards and alerts per agent

## Guidance for agents
Let path filters trigger evaluations.

**Do**
```yaml
paths: [backend/src/ai_gateway/**, backend/src/agents/**, prompts/**]
```

**Don't**
```yaml
# prompt edited with no evaluation run
```

## Revisit when
Never expected to change.

## Related
- ADR-074
- ADR-081
