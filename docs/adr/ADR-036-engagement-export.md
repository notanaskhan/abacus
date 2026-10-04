---
id: ADR-036
title: Engagement export in an open format
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
Firms must retain documentation independently of any vendor and need binder-ready packages. Portability also builds trust.

## Decision
Firms can export any engagement as an open, documented package: evidence files, an index, provenance records and the audit trail. Exports require fresh MFA, are audited, and are delivered through short-lived links. The same mechanism powers binder export.

## Options considered
### Open-format export — chosen
- Pros: Portability; binder feature; trust
- Cons: Format to maintain
- Chosen.

### Proprietary export
- Pros: Lock-in
- Cons: Damages trust and adoption
- Rejected.

## Consequences
**Positive**
- Firms can always leave with their records

**Negative / costs accepted**
- Format versioning

**Follow-up work**
- Export format specification

## Enforcement
- Export format has a versioned schema with tests
- Export action requires `mfa_recent` in the matrix

## Guidance for agents
Generate exports through the export service.

**Do**
```python
await exports.create(ctx, engagement_id)
```

**Don't**
```python
zip_folder(f's3://evidence/{engagement_id}')
```

## Revisit when
Never expected to change.

## Related
- ADR-031
- ADR-034
