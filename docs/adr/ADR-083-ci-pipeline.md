---
id: ADR-083
title: Five-stage CI pipeline and banned-pattern lints
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
Gates must be fast enough to run constantly and complete enough to enforce the decision records.

## Decision
Stage 1 (every commit, under 5 minutes): formatting, linting, strict types, module boundaries, banned-pattern lints, secrets scan, dependency allowlist, document schema validation, classification tags. Stage 2 (every PR, under 15 minutes): unit, property, frontend, permission, route, drift, migration, schema, integration and replay tests with coverage floors. Stage 3 (path-triggered): evaluations, cost regression, security, dependency, licence, infrastructure and container scans. Stage 4 (amber and red): reviewer agents, cross-model review, human approval. Stage 5 (nightly): full evaluations, mutation testing, end-to-end, connector contracts, performance, accessibility. `make check` runs stages 1 and 2. Banned-pattern lints are extended whenever an agent repeats a mistake.

## Options considered
### Staged pipeline — chosen
- Pros: Fast feedback plus depth
- Cons: Pipeline maintenance
- Chosen.

## Consequences
**Positive**
- Every ADR enforcement point runs automatically

**Negative / costs accepted**
- CI infrastructure cost

## Enforcement
- Required checks configured on the main branch
- Stage time budgets monitored; overruns raise an issue

## Guidance for agents
Run the same gates locally that CI runs.

**Do**
```bash
make check
```

**Don't**
```bash
git commit --no-verify
```

## Revisit when
Never expected to change.

## Related
- ADR-010
- ADR-079
- ADR-080
