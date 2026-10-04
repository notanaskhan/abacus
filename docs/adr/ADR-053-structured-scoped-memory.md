---
id: ADR-053
title: Structured, attributed and scoped memory
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
Agents need engagement and firm memory, but memory that is unstructured, unattributed or unscoped becomes wrong, untraceable or leaky.

## Decision
Memory has four kinds: working (workflow state), engagement (structured facts carried to next year), firm (examples, approved rules, evaluation cases) and knowledge (methodology documents via vector search). Facts are stored in tables; vectors are used only for recall. Every memory is attributed to its source and scoped to firm, client or engagement. Retrieval goes through `visible()`. Agents propose memories; humans confirm important ones. No learning across firms.

## Options considered
### Structured scoped memory — chosen
- Pros: Correctable, auditable, isolated
- Cons: Schema work
- Chosen.

### Vector store for everything
- Pros: Simple
- Cons: Unqueryable facts; weak attribution and scoping
- Rejected.

## Consequences
**Positive**
- Memory is traceable and correctable
- Tenancy and walls apply to memory

**Negative / costs accepted**
- Memory schemas to maintain

## Enforcement
- Memory tables carry `tenant_id`, scope and `source_ref` NOT NULL
- Retrieval functions require `visible()`; test for cross-tenant retrieval returning nothing
- No shared embedding index across tenants

## Guidance for agents
Store facts as attributed records.

**Do**
```python
memory.propose_fact(ctx, engagement_id, kind='bank_accounts', value=['4471','2290','8812'], source_ref=evidence_version_id)
```

**Don't**
```python
vector_store.add('client has 3 bank accounts')
```

## Revisit when
Cross-firm learning is proposed with explicit consent mechanisms.

## Related
- ADR-014
- ADR-027
