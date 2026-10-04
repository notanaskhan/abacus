---
id: ADR-004
title: Evidence and ledger data are versioned and immutable
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
Audit evidence must be provably unaltered. Clients revise their books after evidence is received, and the system must show both what was accepted and what changed.

## Decision
`EvidenceVersion` rows and `LedgerSnapshot` data are insert-only. Corrections and re-pulls create new versions; the old version is marked superseded, never modified. Files are stored write-once (ADR-016). Nothing inside an active or archived engagement is deleted except by the retention policy process.

## Options considered
### Immutable versions — chosen
- Pros: Provable integrity; complete history; supports change detection
- Cons: More storage
- Chosen.

### Overwrite in place
- Pros: Less storage
- Cons: Destroys evidence history; indefensible in review or inspection
- Rejected.

## Consequences
**Positive**
- Integrity is guaranteed by the database and storage, not just code
- Change detection becomes a comparison between versions

**Negative / costs accepted**
- Storage grows with every re-pull

**Follow-up work**
- Retention policy process (topic 3)

## Enforcement
- The application database role has no UPDATE or DELETE privilege on `evidence_versions` and ledger snapshot tables
- Database trigger rejects updates to immutable columns as a second layer
- Test: attempting to update a stored version raises an error
- Protected path: changes to these tables' privileges require human approval (hook)

## Guidance for agents
Create a new version; never edit an existing one.

**Do**
```python
evidence_service.add_version(ctx, evidence_item_id, file, provenance)
```

**Don't**
```python
version.file_key = new_key; session.commit()
```

## Revisit when
Never expected to change.

## Related
- ADR-007
- ADR-016
