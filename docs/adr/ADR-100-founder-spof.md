---
id: ADR-100
title: Mitigating founder single point of failure
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
A solo founder is the largest single point of failure in operations.

## Decision
All operational knowledge is documented in runbooks, decisions and dashboards. On-call is scoped to SEV1 and SEV2 pages, with extended coverage in busy season. Operational help — a fractional operations or reliability engineer, or a managed partner — is in place before the second busy season.

## Options considered
### Document and plan help — chosen
- Pros: Reduces dependence on one person
- Cons: Cost of help
- Chosen.

## Consequences
**Positive**
- Continuity if the founder is unavailable

**Negative / costs accepted**
- Budget for operational support

**Follow-up work**
- Engage operational support before the second busy season

## Enforcement
- Readiness checklist includes a second-person runbook walkthrough

## Guidance for agents
Write it down as you learn it.

**Do**
```python
# runbook updated after resolving the queue backlog
```

**Don't**
```python
# fix applied from memory, nothing recorded
```

## Revisit when
Team grows to include operations staff.

## Related
- ADR-098
