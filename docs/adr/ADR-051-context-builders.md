---
id: ADR-051
title: Context assembled by code in five cache-friendly layers
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
Context quality drives accuracy; context size drives cost. Prompt caching rewards stable prefixes.

## Decision
Context builders assemble every model call in this order: instructions, firm context, engagement context, examples, task input. Each layer has a token budget; truncation follows defined rules and is logged. Large documents are pre-processed to select relevant parts. Decision-relevant assembled context is stored with the engagement (ADR-032).

## Options considered
### Layered builders — chosen
- Pros: Accurate, cacheable, reproducible
- Cons: Builder code per task
- Chosen.

### Ad hoc prompt assembly
- Pros: Fast
- Cons: Inconsistent, uncacheable, unreproducible
- Rejected.

## Consequences
**Positive**
- Large cost savings from caching
- Every decision's inputs can be shown

**Negative / costs accepted**
- Builder maintenance

## Enforcement
- Builders are the only way to construct gateway inputs
- Test asserts layer order and budgets
- Stored context hash recorded on each decision-relevant agent run

## Guidance for agents
Build context through the builder.

**Do**
```python
ctx_in = ScreeningContext.build(ctx, request_item, version)
await ai.run(ctx, prompt='evidence.screen@v3', context=ctx_in, ...)
```

**Don't**
```python
prompt = f'{doc_text}\n\nYou are an auditor. {instructions}'  # dynamic content first, ad hoc
```

## Revisit when
Never expected to change.

## Related
- ADR-019
- ADR-032
- ADR-055
