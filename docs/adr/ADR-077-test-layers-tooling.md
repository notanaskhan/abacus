---
id: ADR-077
title: Test layers and tooling
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
Each risk needs the right kind of test; consistent tooling keeps coding agents productive.

## Decision
Unit tests with pytest; property tests with Hypothesis; integration tests against real Postgres with row-level security and write-once storage via containers; Temporal replay and time-skipping tests for workflows and engagement agents; contract tests for the API client and connectors; frontend tests with Vitest and React Testing Library; a small set of Playwright end-to-end journeys with automated accessibility checks; query-count assertions for N+1 detection.

## Options considered
### Layered suite — chosen
- Pros: Right test for each risk
- Cons: Several tools
- Chosen.

### Mostly end-to-end
- Pros: Realistic
- Cons: Slow and flaky
- Rejected.

## Consequences
**Positive**
- Fast feedback with deep coverage where it matters

**Negative / costs accepted**
- Tooling to maintain

## Enforcement
- CI stage definitions run each layer
- Critical journeys list maintained in `docs/architecture/e2e-journeys.md`

## Guidance for agents
Use time-skipping for long-running agent behaviour.

**Do**
```python
async with await WorkflowEnvironment.start_time_skipping() as env:
    # simulate three silent weeks and assert reminders and escalation
```

**Don't**
```python
await asyncio.sleep(60*60*24*21)  # real waiting
```

## Revisit when
Tooling ecosystem changes.

## Related
- ADR-017
- ADR-062
- ADR-076
