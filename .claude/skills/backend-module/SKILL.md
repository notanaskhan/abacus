---
name: backend-module
description: How to add or extend a backend module — layering, public API, tenancy, authorisation, unit of work. Use when creating a module, service, repository or route.
---

# Backend module pattern

**Reference implementation:** `docs/architecture/reference/backend-module.md` (written from the walking skeleton — read it first; if it doesn't exist yet, stop and ask).

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
- Shared infrastructure comes from the kernel (`from abacus.kernel.uow import …`); other modules only via `from abacus.modules.<m>.api import …` (ADR-101).

## Checklist before done
- [ ] Cross-tenant test for every repository method
- [ ] Permission tests regenerate cleanly from the matrix
- [ ] Module README updated
