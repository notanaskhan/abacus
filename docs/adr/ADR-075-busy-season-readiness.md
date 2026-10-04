---
id: ADR-075
title: Busy-season readiness
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
January to March concentrates load; failures then damage reputation most.

## Decision
Each December, a load test simulates peak volumes: many firms, dozens of engagements each, full request lists, simultaneous connections. Provider rate-limit increases are requested well in advance.

## Options considered
### Annual readiness programme — chosen
- Pros: Problems found before customers feel them
- Cons: Annual effort
- Chosen.

## Consequences
**Positive**
- Confidence entering busy season

**Negative / costs accepted**
- Load-test infrastructure

**Follow-up work**
- Synthetic peak simulation

## Enforcement
- Readiness checklist tracked as a task with sign-off
- Load-test results stored with pass/fail thresholds

## Guidance for agents
Run the readiness checklist each December.

**Do**
```bash
make loadtest PROFILE=busy-season
```

**Don't**
```bash
# discovering limits in February
```

## Revisit when
Load patterns change.

## Related
- ADR-043
- ADR-071
- ADR-072
