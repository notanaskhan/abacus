---
id: ADR-096
title: Backups, disaster recovery and integrity verification
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
Evidence must survive infrastructure failures and be provably unchanged after recovery.

## Decision
Postgres runs across data centres with automatic failover and 35-day point-in-time recovery, with encrypted backup copies in a second US region. Evidence storage uses versioning and write-once retention, replicated to a second US region. Encryption keys exist in both regions, and crypto-shredding destroys them everywhere. Quarterly restore drills restore into an isolated environment and verify control totals and evidence fingerprints. A periodic sweep re-fingerprints stored evidence.

## Options considered
### Verified DR — chosen
- Pros: Recovery proven, integrity provable
- Cons: Drill effort
- Chosen.

## Consequences
**Positive**
- Recoverable and verifiable data

**Negative / costs accepted**
- Cross-region storage cost

## Enforcement
- Restore drill recorded with results each quarter
- Integrity sweep alerts on any fingerprint mismatch

## Guidance for agents
Verify restores with fingerprints and control totals.

**Do**
```python
assert sha256(restored_file) == version.sha256
```

**Don't**
```python
# restore declared successful because the database started
```

## Revisit when
Never expected to change.

## Related
- ADR-016
- ADR-034
- ADR-035
- ADR-095
