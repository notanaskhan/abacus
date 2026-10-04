---
id: ADR-045
title: First ledger chosen from data; direct connectors plus a unified API
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
Audited companies skew larger than typical small-business ledger users. The first ledger should match where target firms' audit clients actually are.

## Decision
The first connector is chosen from discovery data on which ledgers target firms' audit clients use. The top two or three ledgers get deep direct connectors. A unified accounting API later provides basic coverage for the long tail.

## Options considered
### Data-driven, direct + unified — chosen
- Pros: Depth where it matters; breadth elsewhere
- Cons: Two integration styles
- Chosen.

### Unified API only
- Pros: Fast breadth
- Cons: Too shallow for attachments and detailed reports
- Rejected.

### Assume QuickBooks Online
- Pros: Simple
- Cons: May not match audit clients
- Rejected.

## Consequences
**Positive**
- Effort follows actual client distribution

**Negative / costs accepted**
- Discovery data required before building

**Follow-up work**
- Ledger question in every discovery call

## Enforcement
- The first connector spec must cite the discovery data

## Guidance for agents
Ground connector priorities in recorded discovery data.

**Do**
```python
# SPEC-00X cites: 10 firms, ledger share table
```

**Don't**
```python
# building a connector because it seemed popular
```

## Revisit when
Client distribution shifts or a unified API reaches sufficient depth.

## Related
- ADR-037
