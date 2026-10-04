---
id: ADR-066
title: Citations are verified by code
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
Fabricated citations — pages, quotes or figures that don't exist — are the most damaging failure in an evidence product.

## Decision
Every citation in agent output is verified deterministically before display: the cited page, cell or transaction must exist; quoted text must appear in the source; cited numbers must equal code-computed values. Failing citations are marked unverified and never presented as fact.

## Options considered
### Deterministic verification — chosen
- Pros: Strong, cheap defence against fabrication
- Cons: Citation formats must be structured
- Chosen.

### Trust model citations
- Pros: None
- Cons: Fabrication reaches reviewers
- Rejected.

## Consequences
**Positive**
- Reviewers can rely on what is shown as cited

**Negative / costs accepted**
- Structured citation schema required

## Enforcement
- `Citation` is a typed structure with source references; a verifier runs on every handoff
- Evaluation cases include deliberately fabricated citations

## Guidance for agents
Return structured citations; let the verifier check them.

**Do**
```python
Citation(evidence_version_id=v, page=3, quote='Balance at 31 Dec')
```

**Don't**
```python
rationale='See page 3, which shows the balance'
```

## Revisit when
Never expected to change.

## Related
- ADR-050
- ADR-054
