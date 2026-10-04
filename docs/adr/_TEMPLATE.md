<!-- Location in repo: docs/adr/_TEMPLATE.md -->
<!-- Copy to docs/adr/ADR-XXX-short-name.md. Numbers are never reused. -->

---
id: ADR-XXX
title: <Decision in a few words>
status: proposed         # proposed | accepted | superseded by ADR-YYY | deprecated
date: YYYY-MM-DD
deciders: <names>
risk_zone: amber         # green | amber | red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, **stop** and raise it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
<What problem forces this decision? What constraints apply — technical, regulatory, commercial, team size? What happens if we don't decide?>

## Decision
<One clear statement, written as a rule. e.g. "All database access goes through module repositories; no module queries another module's tables.">

## Options considered
### Option A: <name> — chosen
- Pros:
- Cons:

### Option B: <name>
- Pros:
- Cons:
- Why rejected:

### Option C: <name>
- Pros:
- Cons:
- Why rejected:

## Consequences
**Positive**
- 

**Negative / costs accepted**
- 

**Follow-up work created**
- 

## Enforcement
How this decision is mechanically enforced. If it can't be enforced, say why and how it's checked instead.
- [ ] Lint rule:
- [ ] Architecture / dependency rule in CI:
- [ ] Test:
- [ ] Hook or protected path:
- [ ] Reviewer agent checklist item:
- [ ] Advisory only — reason:

## Guidance for agents
<A short paragraph on what this means for code being written today.>

**Do**
```
<small example of the correct pattern>
```

**Don't**
```
<small example of the forbidden pattern>
```

## Revisit when
<Conditions that would justify reopening this decision, e.g. "more than 500 tenants", "a second ledger integration", "SOC 2 Type II audit begins".>

## Related
- ADRs:
- Specs:
- Docs:
