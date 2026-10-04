---
id: ADR-068
title: Learning-loop safeguards
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
Reviewer corrections improve agents, but a single careless or malicious correction should not permanently change firm-wide behaviour.

## Decision
Corrections become retrievable examples immediately. They become firm rules only after manager approval and passing the evaluation suite. Firm rules are versioned and reversible.

## Options considered
### Approval and evaluation gate — chosen
- Pros: Learning without poisoning
- Cons: Slower rule adoption
- Chosen.

### Automatic rule creation
- Pros: Fast
- Cons: One bad correction retrains the firm
- Rejected.

## Consequences
**Positive**
- Firm behaviour changes deliberately

**Negative / costs accepted**
- Rule review workload for managers

## Enforcement
- Firm rule activation requires approver role and passing eval run ID
- Rule history is append-only with rollback

## Guidance for agents
Propose rules; activate through approval.

**Do**
```python
await firm_rules.propose(ctx, rule); await firm_rules.activate(ctx_manager, rule_id, eval_run_id)
```

**Don't**
```python
firm_rules.save(rule, active=True)
```

## Revisit when
Never expected to change.

## Related
- ADR-053
- ADR-054
