---
id: ADR-008
title: Modular monolith
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
A solo founder building with AI coding agents needs a codebase agents can understand and change safely. Microservices add distributed-systems problems the product doesn't have.

## Decision
One deployable backend containing twelve modules: identity, organisations, engagements, requests, evidence, connections, ledger, sampling, agents, audit_trail, communications, platform. The API and the workflow workers run the same modules from different entry points. Each module exposes only its `api` package; no module imports another's internals or touches its tables. Cross-module asynchronous work uses domain events.

## Options considered
### Modular monolith — chosen
- Pros: One codebase; simple operations; clean boundaries
- Cons: Requires discipline to keep boundaries
- Chosen.

### Microservices
- Pros: Independent scaling
- Cons: Distributed complexity; far harder for agents
- Rejected.

### Unstructured monolith
- Pros: Fastest start
- Cons: Decays into a tangle
- Rejected.

## Consequences
**Positive**
- Agents work in one coherent codebase
- Modules can be extracted later

**Negative / costs accepted**
- Boundaries need tooling to stay clean

## Enforcement
- Import contracts (import-linter) in CI: modules import only other modules' `api` packages
- Each module owns tables prefixed with its name; reviewer checklist flags cross-module table access
- Module layout is standard: `api.py`, `service.py`, `models.py`, `repository.py`, `routes.py`, `events.py`, `workflows.py`, `README.md`

## Guidance for agents
Call other modules only through their public `api`.

**Do**
```python
from modules.evidence.api import add_version
```

**Don't**
```python
from modules.evidence.repository import EvidenceRepository
```

## Revisit when
A module needs independent scaling or a separate team owns it.

## Related
- ADR-010
- ADR-012
- ADR-018
