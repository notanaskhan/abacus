---
id: ADR-009
title: Python for the backend, TypeScript for the frontend, strict typing in both
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
The product's roadmap is data-heavy: ledger analysis, statistical sampling, population analytics and document extraction, where Python's ecosystem is strongest. The frontend is a React SPA.

## Decision
Backend and workers use Python 3.12+. The frontend uses TypeScript. Both run with strict typing enforced in CI.

## Options considered
### Python backend + TypeScript frontend — chosen
- Pros: Best data and AI ecosystem; Pydantic for schemas
- Cons: Two languages
- Chosen.

### TypeScript everywhere
- Pros: One language
- Cons: Weak for financial data and document processing
- Rejected.

## Consequences
**Positive**
- Strong tooling for analytics, sampling and documents

**Negative / costs accepted**
- Two toolchains; types shared via generated client

## Enforcement
- Pyright in strict mode and Ruff in CI; `Any` and `type: ignore` require an explanatory comment
- TypeScript `strict: true`; ESLint and Prettier in CI
- `make check` runs both

## Guidance for agents
Fully type every function signature.

**Do**
```python
def trial_balance(ctx: Ctx, entity_id: UUID, period: Period) -> TrialBalance: ...
```

**Don't**
```python
def trial_balance(ctx, entity_id, period): ...
```

## Revisit when
A component's performance needs justify a different language for that component alone.

## Related
- ADR-010
- ADR-012
