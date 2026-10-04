---
id: ADR-003
title: Requests and evidence are linked many-to-many through fulfilments
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
One request (December bank statements) may need several evidence items; one evidence item (GL detail) may satisfy several requests. A direct one-to-one link breaks under real engagements and is costly to undo.

## Decision
`RequestItem` and `EvidenceItem` never reference each other directly. A `Fulfilment` links them and records who created the link (`human`, `agent` or `rule`) and who confirmed it. Agent-created fulfilments are proposals until a human confirms them, either directly or by accepting the request item.

## Options considered
### Fulfilment join entity — chosen
- Pros: Models reality; records how each link was made
- Cons: One extra entity
- Chosen.

### Foreign key from evidence to request
- Pros: Simplest
- Cons: Cannot represent one-to-many or many-to-many; rework later
- Rejected.

## Consequences
**Positive**
- Accurate model of real evidence
- A clear trail of how evidence was matched

**Negative / costs accepted**
- Queries need a join

## Enforcement
- Schema has no `request_item_id` column on `evidence_items` and no `evidence_item_id` on `request_items`
- `fulfilments.created_by_kind` is constrained to `human`, `agent`, `rule`
- Test: an agent-created fulfilment is not counted as confirmed until a human action confirms it

## Guidance for agents
Always link through the fulfilments service.

**Do**
```python
fulfilments_service.propose(ctx, request_item_id, evidence_item_id, created_by_kind='agent')
```

**Don't**
```python
evidence.request_item_id = request.id
```

## Revisit when
Never expected to change.

## Related
- ADR-005
- glossary
