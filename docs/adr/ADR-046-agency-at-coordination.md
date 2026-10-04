---
id: ADR-046
title: Agency at the coordination level, reliability at the step level
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
An agentic product must act autonomously over weeks, yet each individual step must be predictable, cheap and explainable to a reviewer.

## Decision
Autonomy lives in the engagement agent (ADR-058), which decides what to do, when and in what order. Specialist capabilities are workflows with model steps unless the task's path genuinely cannot be predetermined, in which case they are agent loops. In the MVP, the support finder is the only loop.

## Options considered
### Autonomous at the top, deterministic at the bottom — chosen
- Pros: Agentic and reliable
- Cons: Requires clear layering
- Chosen.

### Every capability as an open-ended loop
- Pros: Maximally flexible
- Cons: Unpredictable, costly, hard to test or explain
- Rejected.

### Workflows only, no agent layer
- Pros: Predictable
- Cons: Not agentic; no initiative across the engagement
- Rejected.

## Consequences
**Positive**
- Initiative and coordination without sacrificing step reliability

**Negative / costs accepted**
- Two levels of design

## Enforcement
- Each agent spec declares `shape: workflow` or `shape: loop`; a loop requires a written justification
- Reviewer checklist rejects loops where a fixed path would work

## Guidance for agents
Default specialists to workflow shape.

**Do**
```yaml
shape: workflow   # screener: fixed checklist plus one judgement
```

**Don't**
```yaml
shape: loop       # screener: model decides its own steps for a fixed checklist
```

## Revisit when
Specialist tasks become too varied to express as fixed paths.

## Related
- ADR-047
- ADR-058
