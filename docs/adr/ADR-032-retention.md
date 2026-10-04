---
id: ADR-032
title: Firm-configurable retention with enforced minimums
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
US auditing standards require private company audit documentation be retained at least five years from report release; PCAOB requires seven years for public company audits. States and firm policies may add requirements.

## Decision
Retention is configured per engagement type by the firm, with platform-enforced minimums the firm cannot shorten (five years for private company audits; seven for public company audits). Default is seven years. Evidence, provenance, ledger snapshots, raw payloads, engagement audit events and decision-relevant agent runs share the engagement's retention. Raw model traces ~30 days; security logs at least one year; notifications ~90 days; connector credentials deleted on revocation or expiry; backups ~35 days. Archiving tracks the 60-day documentation completion deadline.

## Options considered
### Configurable with floors — chosen
- Pros: Meets obligations; flexible
- Cons: Configuration to maintain
- Chosen.

### Fixed platform-wide retention
- Pros: Simple
- Cons: Wrong for some firms
- Rejected.

## Consequences
**Positive**
- Firms cannot accidentally under-retain

**Negative / costs accepted**
- Storage cost of long retention

**Follow-up work**
- Retention schedule document; deletion process

## Enforcement
- Retention minimums validated on save; tests cover attempts to shorten below the floor
- Object Lock retention dates derived from engagement retention (ADR-016)

## Guidance for agents
Read retention from the engagement's policy.

**Do**
```python
retain_until = retention.until(engagement)
```

**Don't**
```python
retain_until = archived_at + timedelta(days=365*7)  # hard-coded
```

## Revisit when
Standards or customer requirements change.

## Related
- ADR-016
- ADR-033
- ADR-034
