---
id: ADR-019
title: Thin internal AI gateway
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
Model calls carry client data, cost money, can be manipulated by untrusted content, and must be reproducible for review. Large agent frameworks obscure what is sent to models.

## Decision
Every model call goes through `ai_gateway`. Each call declares its purpose, task tier, Pydantic output schema, budget and tenant. The gateway provides provider abstraction, model routing by tier, a versioned prompt registry, schema validation, prompt caching, per-tenant budgets and rate limits, cost metering, and logging of model, prompt version, inputs and outputs. Untrusted content is passed as clearly delimited data, never as instructions. No heavy agent framework is used.

## Options considered
### Thin internal gateway — chosen
- Pros: Full control; testable; secure
- Cons: We build and maintain it
- Chosen.

### Heavy agent framework
- Pros: Fast start
- Cons: Opaque; misused by agents; hard to secure
- Rejected.

## Consequences
**Positive**
- Every model call is governed, costed and reproducible

**Negative / costs accepted**
- Gateway is ours to maintain

**Follow-up work**
- Autonomy policy, evals and cost controls (topics 5–7)

## Enforcement
- import-linter forbids importing provider SDKs anywhere except `ai_gateway`
- The gateway rejects calls missing a schema, budget, purpose or tenant
- Prompts live in the registry with IDs and versions; inline prompt strings in modules fail a lint rule
- Evals run in CI when prompts or models change

## Guidance for agents
Call the gateway with a registered prompt and schema.

**Do**
```python
result = await ai.run(ctx, prompt='evidence.screen@v3', output=ScreeningOutput, tier='small', budget_usd=0.02, inputs={...})
```

**Don't**
```python
from anthropic import Anthropic
client.messages.create(model='...', messages=[{'role': 'user', 'content': f'Check this: {doc_text}'}])
```

## Revisit when
Never expected to change in principle; implementation evolves.

## Related
- ADR-005
- ADR-013
- ADR-022
