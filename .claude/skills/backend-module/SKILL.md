---
name: backend-module
description: How to add or extend a backend module — layering, public API, tenancy, authorisation, unit of work. Use when creating a module, service, repository or route.
---

# Backend module pattern

**Reference implementation:** `docs/architecture/reference/backend-module.md` (worked example: `modules/requests`). Read it first, with `tenancy-and-authz.md`, `unit-of-work.md` and, for evidence, `evidence-storage.md`.

## Layout
```
backend/src/abacus/modules/<name>/
  api.py          public interface — the only thing other modules import
  routes.py       thin FastAPI routes: validate, authorise, call service
  service.py      business rules; uses the unit of work
  repository.py   all database access; tenant-scoped session; visible() on lists
  models.py       SQLAlchemy models and Pydantic schemas, every field classified
  events.py       domain events this module emits
  workflows.py    Temporal workflows, if any
  README.md       purpose, interface, rules
```

## Rules
- Every route declares one action from the permission matrix and depends on the auth context (ADR-012, 027).
- Every list query applies `visible(ctx, Model)` (ADR-027).
- State changes: `with uow(ctx) as tx:` → change → `tx.record(...)` → `tx.emit(...)` (ADR-018).
- New tables: `tenant_id NOT NULL`, row-level security policy, classification on every column (ADR-014, 031).
- Use glossary names for tables, classes and routes.
- Log, trace and report errors the observability way: `.claude/skills/observability/SKILL.md` (ADR-022).
- A new module, a new dependency between modules or a new table needs `MODULE_DEPENDENCIES`, `TABLE_OWNERS` (`abacus_tools/quality/`) and `ROUTERS` (`abacus/api/app.py`) entries: protected paths, so ask for approval first.
- After changing routes or response models: `make generate`; `make check` fails on client drift.
- Shared infrastructure comes from the kernel (`from abacus.kernel.uow import …`); other modules only via `from abacus.modules.<m>.api import …` (ADR-101).

## Checklist before done
- [ ] Cross-tenant test for every repository method
- [ ] Permission tests regenerate cleanly from the matrix
- [ ] Module README updated
