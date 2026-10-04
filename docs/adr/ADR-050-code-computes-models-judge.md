---
id: ADR-050
title: Code computes, models judge
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
Models make plausible arithmetic errors. In audit, a plausible error is the most dangerous kind.

## Decision
All arithmetic on financial data — sums, tie-outs, balances, agings, differences, comparisons — is performed in code. Models receive computed results and make judgements. Raw ledger data is never sent to a model.

## Options considered
### Code computes — chosen
- Pros: Exact numbers; cheaper prompts
- Cons: More code
- Chosen.

### Models compute and judge
- Pros: Less code
- Cons: Unreliable arithmetic
- Rejected.

## Consequences
**Positive**
- Numbers are always exact

**Negative / costs accepted**
- Every analysis needs a code step

## Enforcement
- AI gateway rejects inputs containing ledger datasets above a row threshold
- Reviewer checklist: any prompt asking the model to calculate is rejected

## Guidance for agents
Compute first, then ask for judgement.

**Do**
```python
diff = aging.total - tb.balance('1200')
await ai.run(ctx, prompt='recon.explain@v1', inputs={'difference': diff, 'memo': memo})
```

**Don't**
```python
await ai.run(ctx, prompt='recon@v1', inputs={'aging_rows': rows, 'tb_rows': tb_rows})  # model sums
```

## Revisit when
Never expected to change.

## Related
- ADR-009
- ADR-051
