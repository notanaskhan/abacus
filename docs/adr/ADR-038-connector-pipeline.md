---
id: ADR-038
title: Six-stage pipeline with immutable raw payloads and control totals
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
Retrieved data becomes audit evidence. It must be traceable to its exact source and verified complete before anyone relies on it.

## Decision
Every pull runs: extract → raw → normalise → validate → snapshot → render. Raw provider responses are stored unaltered in write-once storage with fingerprints. Validation must pass before data is used: the trial balance balances; opening balance plus activity equals closing balance per account; GL detail reconciles to the trial balance; all requested periods are present. Failed validation flags the pull and blocks downstream use.

## Options considered
### Staged pipeline with validation — chosen
- Pros: Traceable, verified data
- Cons: More stages to build
- Chosen.

### Map directly from API to evidence
- Pros: Faster
- Cons: No raw trail; unverified completeness
- Rejected.

## Consequences
**Positive**
- Every number traces to original bytes
- Retrieved data is verified in a way uploads never are

**Negative / costs accepted**
- Storage for raw payloads

## Enforcement
- Each stage is a separate activity with typed inputs and outputs
- Validation failures create a flagged sync run; evidence rendering refuses unvalidated snapshots
- Property tests: any normalised trial balance must balance

## Guidance for agents
Pass data stage to stage; never skip validation.

**Do**
```python
snapshot = await validate(normalise(raw))  # raises on failed control totals
```

**Don't**
```python
render_evidence(api_response.json())
```

## Revisit when
Never expected to change.

## Related
- ADR-004
- ADR-016
- ADR-042
