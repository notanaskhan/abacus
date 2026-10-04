---
id: ADR-086
title: Earned autonomy for coding agents
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
Human review of every change does not scale, but autonomy must be justified by evidence.

## Decision
Initially every merge requires human approval. After the gate suite has proved reliable for a defined period with no escaped defects in green-zone code, green-zone pull requests that pass every gate and every reviewer agent may merge automatically. Amber and red changes always require human approval.

## Options considered
### Earned autonomy — chosen
- Pros: Scales review where proven safe
- Cons: Requires tracking escaped defects
- Chosen.

### Human review forever
- Pros: Maximum control
- Cons: Bottleneck
- Rejected.

### Auto-merge from day one
- Pros: Fast
- Cons: Unproven gates
- Rejected.

## Consequences
**Positive**
- Founder time shifts to high-risk changes

**Negative / costs accepted**
- Reliability tracking

**Follow-up work**
- Escaped-defect log

## Enforcement
- Auto-merge rule limited to paths classified green and enabled by a recorded decision
- Any escaped green-zone defect suspends auto-merge pending review

## Guidance for agents
Rely on path-based zone classification.

**Do**
```yaml
zones:
  green: [apps/web/src/components/**, docs/**]
```

**Don't**
```yaml
# auto-merge enabled repository-wide
```

## Revisit when
Never expected to change.

## Related
- ADR-083
- ADR-084
