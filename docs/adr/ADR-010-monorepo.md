---
id: ADR-010
title: Monorepo with enforced boundaries and one command surface
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
Agents need predictable structure and one obvious way to run checks.

## Decision
A single repository:

```
apps/web/                 React SPA
backend/
  src/app/main.py         API entry point
  src/worker/main.py      Temporal worker entry point
  src/modules/<module>/   the twelve modules
  src/platform/           shared kernel: db, auth context, outbox, config, logging
  src/ai_gateway/
  migrations/             Alembic
  tests/
packages/ui/              design system
packages/api-client/      generated from OpenAPI
infra/                    Terraform
evals/
docs/  work/
Makefile
```

Python uses `uv`; the frontend uses `pnpm`. A root `Makefile` is the only command surface: `make check`, `make test`, `make dev`, `make generate`.

## Options considered
### Monorepo — chosen
- Pros: Atomic changes across API and UI; one place for docs
- Cons: Two toolchains in one repo
- Chosen.

### Separate repositories
- Pros: Independent histories
- Cons: Cross-cutting changes span repos; agents lose context
- Rejected.

## Consequences
**Positive**
- One place for code, docs, specs and decisions

**Negative / costs accepted**
- Toolchain setup is slightly more involved

## Enforcement
- `make check` runs every gate; CI runs the same target
- Boundary tools: import-linter (backend), ESLint import rules (frontend)
- Constitution instructs agents to use only Makefile targets

## Guidance for agents
Use Makefile targets.

**Do**
```bash
make check
```

**Don't**
```bash
cd backend && pytest -k some_test  # skipping the full gate set before claiming done
```

## Revisit when
The team grows to several independent groups.

## Related
- ADR-008
- ADR-009
