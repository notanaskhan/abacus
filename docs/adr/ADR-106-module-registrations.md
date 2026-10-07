---
id: ADR-106
title: Modules hand facts to each other by registration, and evidence may depend on requests
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
ADR-008 lets modules depend on each other in one direction only, through `api.py`. Three features need a fact owned by a module that may not be imported:
- **Identity's ethical walls** need an engagement's client, which engagements owns (TASK-016).
- **The kernel's dispatch** needs each workflow's work class, which each module owns (TASK-018).
- **Evidence's review decisions** need the agent's proposal, which agents owns, and agents already depends on evidence (TASK-019).

Review queues also need which version fulfils which request item. That fact is in requests, which evidence did not depend on.

## Decision
- **Registration:** a module that needs a fact owned downstream defines a small typed callback slot and a `register_…` function in its `api.py`. The owning module registers its implementation at import of its own `api.py`. Registering a different implementation twice raises. A missing registration fails closed, and each slot documents how: walls deny, an unregistered workflow can't be dispatched, and review decisions answer 503.
- **The registrations today:**
  - `identity.register_engagement_client` (engagements);
  - `kernel.dispatch.register_work_classes` (connections and agents, in the module that starts the workflow);
  - `evidence.register_proposal_source` (agents).
- **New edge:** evidence may depend on requests (`MODULE_DEPENDENCIES`, BOUND-002). Requests never depends on evidence.

## Options considered
### Registration (dependency inversion) — chosen
- Pros: keeps the one-way module graph; the owner keeps its tables private
- Cons: an import-time side effect, which a process must trigger by importing the owner's `api`
- Chosen.

### A shared view or denormalised column
- Pros: no runtime wiring
- Cons: one module reads another's tables (ADR-008, ADR-103)
- Rejected.

### Merging modules
- Pros: no cross-module call
- Cons: large modules, and agents' and evidence's red-zone code mixed together
- Rejected.

## Consequences
**Positive**
- The module graph stays acyclic and checked (BOUND-002, import contracts)

**Negative / costs accepted**
- Behaviour depends on import order. Each slot has a test for the unregistered case.

## Enforcement
- Tests:
  - each slot fails closed when unregistered;
  - registering twice with a different implementation raises.
- BOUND-002's `MODULE_DEPENDENCIES` is protected, and a test pins it.
- Reviewer checklist: a new registration names its fail-closed behaviour.

## Guidance for agents
**Do**
```python
# in the owning module's api.py
register_proposal_source(proposals_for, proposal_of)
```

**Don't**
```python
from abacus.modules.agents.repository import latest_results  # evidence reading agents' tables
```

## Revisit when
A module needs more than two registrations from the same owner: consider moving the fact.

## Related
- ADR-008
- ADR-101
- ADR-103
- ADR-026
- ADR-071
- SPEC-004
