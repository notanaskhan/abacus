---
id: ADR-035
title: Per-tenant encryption keys for restricted data
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
Evidence and connector credentials are the most sensitive data. Isolation should survive storage-level mistakes, and offboarding must render data unreadable even where bytes cannot be deleted immediately.

## Decision
Each firm has its own KMS key. Evidence files are encrypted under it (SSE-KMS per object) and connector credentials use envelope encryption with it. Ledger rows in Postgres rely on database encryption and row-level security. Destroying a firm's key on offboarding crypto-shreds its restricted data, including in backups and write-once storage.

## Options considered
### Per-tenant keys — chosen
- Pros: Isolation in depth; crypto-shredding
- Cons: Key management
- Chosen.

### Single platform key
- Pros: Simple
- Cons: No crypto-shredding; weaker isolation
- Rejected.

### Per-field encryption of all ledger rows
- Pros: Maximal
- Cons: High cost, little gain over RLS
- Rejected.

## Consequences
**Positive**
- Cross-tenant storage errors yield unreadable data
- Final offboarding

**Negative / costs accepted**
- Key lifecycle to manage

## Enforcement
- Storage service requires a tenant key reference; uploads without it fail
- Key policies restrict use to the application role; key deletion requires dual control

## Guidance for agents
Encrypt through the storage and secrets services with the tenant key.

**Do**
```python
await evidence_storage.put(ctx, content)  # resolves ctx tenant key
```

**Don't**
```python
s3.put_object(..., ServerSideEncryption='aws:kms')  # default platform key
```

## Revisit when
Customers require their own managed keys (bring-your-own-key).

## Related
- ADR-016
- ADR-021
- ADR-034
