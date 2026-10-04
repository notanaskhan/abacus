---
id: ADR-001
title: Client records are owned by each firm
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
The same real-world company may be audited by one firm and have its taxes prepared by another. Client financial data is confidential to each firm-client relationship, and independence rules make cross-firm visibility unacceptable.

## Decision
Every `Client` and `ClientEntity` record belongs to exactly one firm (tenant). Records are never shared, merged or deduplicated across firms, even when they describe the same legal company.

## Options considered
### Firm-owned records — chosen
- Pros: Hard isolation; simple mental model; no consent complexity
- Cons: Duplicate records and connections when two firms serve one company
- Chosen.

### Global client registry shared across firms
- Pros: One record and one connection per company
- Cons: Cross-firm leakage risk; complex consent; independence exposure
- Rejected: confidentiality risk is unacceptable.

## Consequences
**Positive**
- Isolation is structural rather than policy-based
- Deleting or exporting one firm's data never touches another's

**Negative / costs accepted**
- A client served by two firms connects its systems twice

## Enforcement
- `tenant_id` is NOT NULL on `clients` and `client_entities`, covered by row-level security (ADR-014)
- No uniqueness constraint on tax identifiers across tenants; uniqueness is scoped to `(tenant_id, tax_id)`
- Integration test: two firms create clients with identical names and tax IDs; neither can read the other's
- Security reviewer checklist: no query looks up clients without tenant scope

## Guidance for agents
Clients are always created and queried within the current tenant context.

**Do**
```python
client = clients_service.create(ctx, name=..., tax_id=...)  # ctx carries tenant_id
```

**Don't**
```python
client = session.query(Client).filter_by(tax_id=tax_id).first()  # global lookup across firms
```

## Revisit when
A client explicitly asks to share one connection across its auditors — that requires a separate consent model and a new ADR.

## Related
- ADR-002
- ADR-014
- ADR-020
