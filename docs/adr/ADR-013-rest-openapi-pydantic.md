---
id: ADR-013
title: REST and OpenAPI, with Pydantic as the schema source of truth
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
The frontend needs typed access to the API, and the product will need a clean external API for partners and integrations.

## Decision
The API is REST, versioned under `/v1`. Pydantic models are the single source of truth for request and response schemas. FastAPI emits the OpenAPI spec; `packages/api-client` is generated from it. Model outputs are also validated with Pydantic (ADR-019).

## Options considered
### REST + OpenAPI — chosen
- Pros: Standard; external-ready; typed client via generation
- Cons: Generation step
- Chosen.

### GraphQL
- Pros: Flexible queries
- Cons: Harder authorisation per field; more surface for agents to get wrong
- Rejected.

## Consequences
**Positive**
- Typed frontend without sharing a language
- External API ready when needed

**Negative / costs accepted**
- Generated client must be kept in sync

## Enforcement
- CI regenerates the client and fails if the result differs from the committed version
- Breaking changes require a new API version

## Guidance for agents
Define schemas in Pydantic; regenerate the client.

**Do**
```python
class RequestItemOut(BaseModel):
    id: UUID
    status: RequestItemStatus
```

**Don't**
```python
return {'id': str(item.id), 'status': item.status}  # untyped response
```

## Revisit when
A partner integration needs a different protocol, such as an MCP server alongside REST.

## Related
- ADR-011
- ADR-012
- ADR-019
