---
id: ADR-028
title: No standing platform-staff access; audited break-glass
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
Firms entrust the platform with client financial data. Platform staff with permanent access are a trust and compliance liability.

## Decision
Platform staff have no standing access to customer data. Support access uses break-glass sessions: time-limited, requiring a stated reason, visible to the firm, and fully audited. Infrastructure administration uses separate roles that do not read application data.

## Options considered
### Break-glass only — chosen
- Pros: Strong trust and SOC 2 posture
- Cons: Slower support
- Chosen.

### Standing support access
- Pros: Fast support
- Cons: Unacceptable to regulated customers
- Rejected.

## Consequences
**Positive**
- A clear answer to every due-diligence question about staff access

**Negative / costs accepted**
- Support needs a request step

**Follow-up work**
- Break-glass tooling and firm notification

## Enforcement
- Production database and storage access granted only through time-bound roles, alarmed on use
- Break-glass sessions write audit events visible in the firm's audit log
- Quarterly access review recorded for SOC 2

## Guidance for agents
Use the break-glass flow for any support access.

**Do**
```python
support.open_session(firm_id, reason='ticket-412', duration='1h')
```

**Don't**
```python
psql $PROD_DATABASE_URL  # direct production access
```

## Revisit when
Never expected to change.

## Related
- ADR-021
- ADR-030
