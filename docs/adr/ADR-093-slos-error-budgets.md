---
id: ADR-093
title: Reliability targets, error budgets and paging policy
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
A solo operator must be woken only for problems customers feel, and reliability needs explicit targets.

## Decision
Reliability targets live in `docs/ops/slos.md`: 99.9% monthly API availability; interactive screening 95% within 30 seconds; initial ledger pull within one hour for a typical company; at least daily syncs during active engagements; approved follow-ups sent within 15 minutes; RPO 5 minutes; automatic recovery from single data-centre failure; regional recovery within 8 hours. Exhausting an error budget pauses feature work. Paging occurs only on customer-impacting target burn; all else becomes a ticket.

## Options considered
### SLO-based operations — chosen
- Pros: Focus and sustainable on-call
- Cons: Measurement setup
- Chosen.

## Consequences
**Positive**
- Clear reliability expectations

**Negative / costs accepted**
- Instrumentation work

## Enforcement
- SLOs defined as code with burn-rate alerts
- Alert definitions must reference an SLO or be ticket-only

## Guidance for agents
Alert on SLO burn.

**Do**
```yaml
alert: screening_latency_burn_fast  # pages
```

**Don't**
```yaml
alert: cpu_above_70_percent  # pages at 3am
```

## Revisit when
Targets tighten as the platform matures.

## Related
- ADR-094
