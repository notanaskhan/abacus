---
id: ADR-056
title: No licensed standards text without a licence
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
Official US auditing standards text is copyrighted. Loading it into retrieval without a licence creates legal exposure.

## Decision
The knowledge layer uses each firm's own methodology documents and publicly available material. Licensed standards content is added only under a licence agreement.

## Options considered
### Licence-first — chosen
- Pros: No legal exposure
- Cons: Thinner initial knowledge
- Chosen.

## Consequences
**Positive**
- No copyright risk

**Negative / costs accepted**
- Agents rely on firm methodology for standards references

**Follow-up work**
- Evaluate licensing when needed

## Enforcement
- Knowledge ingestion records source and licence status; unlicensed copyrighted sources are rejected

## Guidance for agents
Ingest firm-provided and public sources only.

**Do**
```python
knowledge.ingest(ctx, doc, source='firm_methodology', licence='firm_owned')
```

**Don't**
```python
knowledge.ingest(ctx, scraped_standards_pdf)
```

## Revisit when
A licence is obtained.

## Related
- ADR-053
