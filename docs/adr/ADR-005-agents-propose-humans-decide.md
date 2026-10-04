---
id: ADR-005
title: Agents propose; humans decide
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
Auditors carry professional liability for conclusions. The product's trust model depends on a provable line between machine work and human judgement.

## Decision
Agents may create `ScreeningResult`s, `Suggestion`s, drafts and proposed fulfilments. Only a human actor may create a `ReviewDecision`, accept or reject evidence, mark items not applicable or waived, change an accepted item, or send messages the autonomy policy marks as requiring approval.

## Options considered
### Agents propose, humans decide — chosen
- Pros: Clear liability line; defensible in inspection
- Cons: Some steps need a human click
- Chosen.

### Agents act autonomously with audit logging
- Pros: Faster
- Cons: Blurs liability; unacceptable to firms and regulators
- Rejected.

## Consequences
**Positive**
- A provable separation between machine and human work

**Negative / costs accepted**
- Throughput is bounded by reviewer capacity

**Follow-up work**
- Autonomy policy configuration (topic 6)

## Enforcement
- Decision-creating service functions require `ctx.actor.kind == 'human'` and raise otherwise
- Database check constraint: `review_decisions.actor_kind = 'human'`
- Agent tool allowlist excludes all decision-making endpoints
- Test: an agent-context call to any decision function fails

## Guidance for agents
Agents return proposals; humans call decision functions.

**Do**
```python
suggestions_service.create(ctx_agent, kind='accept_evidence', target_id=v.id, rationale=...)
```

**Don't**
```python
review_service.accept(ctx_agent, version_id)  # agent making a decision
```

## Revisit when
A future ADR explicitly enumerates specific low-risk actions agents may take autonomously.

## Related
- ADR-003
- ADR-019
