---
id: ADR-041
title: Sync modes and layered change detection
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
Client books change during audits. Missed changes mean accepted evidence silently goes stale.

## Decision
Data is pulled initially on connection, on a schedule while the engagement is active (increasing near fieldwork), and on demand. Change detection uses webhooks as hints, change feeds or polling as the source of truth, and snapshot comparison as verification. When a new snapshot differs from one backing accepted evidence, a change event is created, a new evidence version is generated, and the reviewer is notified.

## Options considered
### Layered detection — chosen
- Pros: Robust to missed webhooks
- Cons: More moving parts
- Chosen.

### Webhooks only
- Pros: Simple
- Cons: Missed events go undetected
- Rejected.

## Consequences
**Positive**
- The close collision is detected, not discovered

**Negative / costs accepted**
- Scheduling and comparison cost

## Enforcement
- Scheduled sync workflows per active connection in Temporal
- Test: a changed closed-period balance after acceptance creates a change event and new version

## Guidance for agents
Treat webhooks as triggers for a verified pull.

**Do**
```python
on_webhook -> start_workflow(IncrementalPull, conn_id)
```

**Don't**
```python
on_webhook -> apply_payload_to_ledger(payload)
```

## Revisit when
Providers offer reliable, complete change streams.

## Related
- ADR-004
- ADR-017
- ADR-038
