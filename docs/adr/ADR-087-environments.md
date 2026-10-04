---
id: ADR-087
title: Separated environments; production data stays in production
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
Staging and local environments are common sources of data leaks when production data is copied for convenience.

## Decision
Three environments: local (containers for Postgres, write-once storage and a Temporal dev server, with fake model and fake connector), staging (production-shaped, synthetic data only), production. Each has its own AWS account, Temporal namespace, model provider keys and budgets. Production data never leaves production.

## Options considered
### Separated environments — chosen
- Pros: Blast radius contained; no data leakage
- Cons: More accounts to manage
- Chosen.

### Shared account with namespacing
- Pros: Simpler
- Cons: Weak isolation; tempting data copies
- Rejected.

## Consequences
**Positive**
- Non-production environments cannot leak client data

**Negative / costs accepted**
- Synthetic data needed for realistic testing

## Enforcement
- Account-level IAM prevents cross-environment data access
- No backup restore path from production into other accounts

## Guidance for agents
Use the synthetic generator for realistic staging data.

**Do**
```bash
make seed-staging PROFILE=busy-season
```

**Don't**
```bash
pg_dump $PROD | psql $STAGING
```

## Revisit when
Never expected to change.

## Related
- ADR-021
- ADR-085
