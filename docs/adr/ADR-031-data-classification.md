---
id: ADR-031
title: Four-level data classification tagged on every field
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
Rules about logging, error tracking, model calls and exports must apply consistently. Scattered rules get forgotten.

## Decision
Data is classified as Restricted (client financial data, evidence, ledger data, messages, connector credentials), Confidential (firm data, metadata, audit events), Internal, or Public. Every Pydantic model field carries a classification tag. Logging, error tracking, exports and the AI gateway read the same tags. Model provider terms must include zero retention and no training before client data is sent.

## Options considered
### Field-level tags — chosen
- Pros: One annotation drives every control
- Cons: Every field must be tagged
- Chosen.

### Policy document only
- Pros: Easy
- Cons: Unenforceable
- Rejected.

## Consequences
**Positive**
- Consistent controls everywhere data flows

**Negative / costs accepted**
- Tagging overhead on every model

**Follow-up work**
- Model provider data-processing terms

## Enforcement
- Test fails if any model field lacks a classification
- Logging helper refuses Restricted fields; Sentry scrubbing driven by tags
- AI gateway accepts Restricted data only on approved routes

## Guidance for agents
Tag every field.

**Do**
```python
class EvidenceVersionOut(BaseModel):
    id: UUID = Field(json_schema_extra={'cls': 'confidential'})
    extracted: dict = Field(json_schema_extra={'cls': 'restricted'})
```

**Don't**
```python
class EvidenceVersionOut(BaseModel):
    id: UUID
    extracted: dict
```

## Revisit when
Never expected to change.

## Related
- ADR-019
- ADR-022
- ADR-036
