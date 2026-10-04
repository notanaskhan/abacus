---
id: ADR-015
title: SQLAlchemy 2.0 and Alembic, with safe migrations
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
Database access must be typed, transparent in review, and compatible with per-transaction tenant settings. Migrations on live data are a common source of incidents.

## Decision
Data access uses SQLAlchemy 2.0 (async) inside module repositories. Schema changes use Alembic. Every migration is reviewed as SQL, is reversible, and follows expand-then-contract for destructive changes.

## Options considered
### SQLAlchemy + Alembic — chosen
- Pros: Mature; typed; works with RLS session settings
- Cons: More verbose than some ORMs
- Chosen.

### Django ORM
- Pros: Productive
- Cons: Ties us to Django
- Rejected.

### Raw SQL only
- Pros: Maximum control
- Cons: Loses typing and consistency
- Rejected.

## Consequences
**Positive**
- Mature, well-understood tooling

**Negative / costs accepted**
- Verbosity

## Enforcement
- CI runs every migration up and down against a real Postgres
- Migration linter blocks unsafe operations (table rewrites, non-concurrent indexes, dropped columns without a contract step)
- Protected path: applied migrations cannot be edited (hook)

## Guidance for agents
Add a new migration; never edit an applied one.

**Do**
```bash
uv run alembic revision -m 'add fulfilment confirmed_by'
```

**Don't**
```bash
# editing migrations/versions/0007_*.py after it has run in staging
```

## Revisit when
Never expected to change.

## Related
- ADR-014
