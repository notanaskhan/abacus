---
id: ADR-097
title: Incident response and kill switches
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
Incidents are inevitable; prepared responses and controls limit damage, especially for data exposure.

## Decision
Severity levels: SEV1 (suspected cross-firm exposure; full outage in busy season), SEV2 (major feature or provider outage), SEV3 (degraded or single firm). Kill switches: platform-wide AI pause, per-firm and per-engagement agent pause, connector provider disable, feature flags, read-only mode. Security incidents follow contain, preserve, assess, notify, with counsel-drafted notification templates and timelines matching DPAs and law. Every incident ends with a blameless written review whose actions become tests, lint rules, alerts or ADRs.

## Options considered
### Prepared response — chosen
- Pros: Faster, safer incident handling
- Cons: Preparation effort
- Chosen.

## Consequences
**Positive**
- Controlled responses under pressure

**Negative / costs accepted**
- Kill switches must be tested

**Follow-up work**
- Notification templates from counsel

## Enforcement
- Kill switches exercised in game days
- Incident reviews tracked to completion

## Guidance for agents
Use kill switches rather than ad hoc fixes.

**Do**
```python
await platform.set_read_only(reason='SEV1-2027-02-04')
```

**Don't**
```python
# hot-patching production code during an incident
```

## Revisit when
Never expected to change.

## Related
- ADR-028
- ADR-062
- ADR-098
