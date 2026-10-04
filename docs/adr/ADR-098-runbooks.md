---
id: ADR-098
title: Rehearsed runbooks for foreseeable scenarios
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
A solo operator under pressure needs written, tested procedures.

## Decision
Runbooks in `docs/runbooks/` for: deploy and rollback, failed migration, model provider outage, connector provider outage, expiring connections wave, queue backlog, cost spike, suspected cross-firm exposure, key compromise and rotation, restore from backup, regional failover, break-glass access, firm offboarding, legal hold, disaster recovery drill, busy-season readiness. Each is linked from relevant alerts and rehearsed.

## Options considered
### Rehearsed runbooks — chosen
- Pros: Reliable response; transferable knowledge
- Cons: Writing and rehearsal time
- Chosen.

## Consequences
**Positive**
- Anyone can follow the procedure

**Negative / costs accepted**
- Maintenance as systems change

## Enforcement
- Alert definitions require a runbook link
- Runbooks record last rehearsal date; stale runbooks raise a ticket

## Guidance for agents
Link alerts to runbooks.

**Do**
```yaml
runbook: docs/runbooks/connector-provider-outage.md
```

**Don't**
```yaml
# alert with no guidance
```

## Revisit when
Never expected to change.

## Related
- ADR-093
- ADR-097
