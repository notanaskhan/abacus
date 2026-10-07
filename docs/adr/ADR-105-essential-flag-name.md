---
id: ADR-105
title: An agent's essential or deferrable flag is named `essential`
status: accepted
date: 2026-10-07
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-069's guidance names an agent's essential or deferrable flag `work_class: essential | deferrable`. ADR-071 uses "work class" for something else: one of four queues (interactive, time-sensitive, background, batch). An agent spec needs both, so one name can't mean two things (SPEC-003 Q2).

## Decision
In agent specs, `work_class` means ADR-071's queue class. ADR-069's flag is `essential: true | false`. This amends only ADR-069's guidance and enforcement wording; its decision is unchanged.

## Options considered
### Rename ADR-069's flag to `essential` — chosen
- Pros: `work_class` keeps the meaning ADR-071 and the dispatch code use; a boolean says what it means
- Cons: ADR-069's example no longer matches the spec field name
- Chosen.

### Rename ADR-071's class (`queue_class`)
- Pros: ADR-069 unchanged
- Cons: "work class" is the term in ADR-071, ADR-072, SPEC-003 and the code
- Rejected.

## Consequences
**Positive**
- One meaning per field

**Negative / costs accepted**
- Readers of ADR-069 need this ADR for the field's name

## Enforcement
- `AgentSpec` requires `work_class` (one of the four classes) and `essential` (a boolean); a spec without either doesn't load

## Guidance for agents
**Do**
```yaml
work_class: time_sensitive
essential: true
```

**Don't**
```yaml
work_class: essential
```

## Revisit when
Never expected to change.

## Related
- ADR-069
- ADR-071
- SPEC-003
