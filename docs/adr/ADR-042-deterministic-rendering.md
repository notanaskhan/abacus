---
id: ADR-042
title: Deterministic evidence rendering
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
Evidence files are fingerprinted. Non-deterministic rendering would create new versions on every re-pull even when data is unchanged, flooding change detection.

## Decision
Rendering is deterministic: identical data produces byte-identical files. Fixed file metadata, stable sort orders, no embedded timestamps other than the pull time. Each file carries a provenance footer: source, pull time, period, snapshot ID and fingerprint.

## Options considered
### Deterministic rendering — chosen
- Pros: Clean versioning and deduplication
- Cons: Care needed with file libraries
- Chosen.

### Library defaults
- Pros: Easy
- Cons: Fingerprint churn
- Rejected.

## Consequences
**Positive**
- Versions change only when data changes

**Negative / costs accepted**
- File library configuration

## Enforcement
- Test renders the same snapshot twice and asserts identical fingerprints

## Guidance for agents
Render through the evidence renderer with fixed metadata.

**Do**
```python
render_xlsx(snapshot, created=snapshot.pulled_at, author='platform')
```

**Don't**
```python
wb.save(path)  # library stamps current time
```

## Revisit when
Never expected to change.

## Related
- ADR-016
- ADR-038
