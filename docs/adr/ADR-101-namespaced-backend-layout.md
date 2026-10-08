---
id: ADR-101
title: Namespaced backend package layout
status: accepted
date: 2026-10-05
deciders: Founder
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking this ADR, **stop** and raise it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
ADR-010 placed backend packages directly under `backend/src/`: `app`, `worker`, `modules`, `platform`, `ai_gateway`, with tooling packages (`quality`, `synthetic`, `loadtest`) beside them. Once `src/` is importable, `platform` shadows Python's standard-library `platform` module (or is shadowed by it), breaking pytest, uvicorn and `import platform.db`. The other flat names (`app`, `worker`, `quality`, `synthetic`, `tests`) are just as liable to collide with third-party distributions that install generic top-level packages.

"Platform" also named two different things: the shared kernel in ADR-010 and the twelfth domain module in ADR-008 and AGENTS.md.

## Decision
All backend product code lives under one root package, `abacus`. Development and operations tooling lives under a second root, `abacus_tools`. Nothing else is importable from `backend/src/`.

```
backend/src/
  abacus/                      the product — the only package in the runtime wheel
    api/                       HTTP entry point (was app/)
    worker/                    Temporal worker entry point
    kernel/                    shared kernel
    modules/<module>/          the thirteen modules (ADR-008)
    ai_gateway/
  abacus_tools/                tooling — never imported by abacus
    quality/                   stage 1 and 2 checkers (was backend/quality/)
    synthetic/                 seeded synthetic data generator (ADR-085)
    loadtest/                  load-test profiles (ADR-075)
```

**Kernel and platform are different things.**
- The **shared kernel**, `abacus.kernel`, holds database sessions, tenant context, unit of work, outbox, encryption, config and logging. It is not a module and not one of the thirteen. Modules use it; it never imports a module.
- **`abacus.modules.platform`** is the twelfth domain module — tenant settings, feature flags, usage metering — exactly as ADR-008 and AGENTS.md list it.

**Layers** (higher may import lower, never the reverse): `abacus.api | abacus.worker` → `abacus.modules` → `abacus.ai_gateway` → `abacus.kernel`.

**Tooling** may import `abacus` public APIs (synthetic seeding and load tests drive the product). `abacus` never imports `abacus_tools`, and `abacus_tools` is excluded from the runtime wheel.

This ADR replaces ADR-010 in full. ADR-010's other decisions carry over unchanged and are restated here so this ADR stands alone:

- **One repository** for the backend, the React SPA (`apps/web/`), the design system (`packages/ui/`), the generated API client (`packages/api-client/`), Terraform (`infra/`), evaluation suites (`evals/`), docs and work items.
- **Toolchains:** Python uses `uv`; the frontend uses `pnpm` workspaces.
- **One command surface:** the root `Makefile` is the only way humans, agents and CI run anything (`make setup`, `make check`, `make test`, `make dev`, `make generate`, …).
- **Boundary tooling:** import-linter for the backend, ESLint import restrictions for the frontend.

```
apps/web/                 React SPA
backend/
  src/abacus/             product code (layout above)
  src/abacus_tools/       tooling
  migrations/             Alembic
  tests/
packages/ui/              design system
packages/api-client/      generated from OpenAPI
infra/                    Terraform
evals/
docs/  work/
Makefile
```

### Path mapping for accepted ADRs
Accepted ADRs are immutable, so their paths and examples are read through this table:

| Written in | As written | Read as |
|---|---|---|
| ADR-010 | `src/app/` | `src/abacus/api/` |
| ADR-010 | `src/worker/` | `src/abacus/worker/` |
| ADR-010 | `src/modules/<module>/` | `src/abacus/modules/<module>/` |
| ADR-010 | `src/platform/` (shared kernel) | `src/abacus/kernel/` |
| ADR-010 | `src/ai_gateway/` | `src/abacus/ai_gateway/` |
| ADR-008 | `from modules.<m>.api import …` | `from abacus.modules.<m>.api import …` |
| ADR-047, ADR-082 | `backend/src/agents/` | `backend/src/abacus/modules/agents/` |
| ADR-082 | `backend/src/ai_gateway/` | `backend/src/abacus/ai_gateway/` |
| ADR-044, ADR-085 | `synthetic.company(...)` | `abacus_tools.synthetic.company(...)` |

ADR-097's example `platform.set_read_only(...)` predates this split; where the kill switch lives is decided when it is built, and it is not the kernel by default.

## Options considered
### Option A: single namespaced root `abacus`, tooling in `abacus_tools` — chosen
- Pros: No top-level name can collide; one obvious import prefix; runtime wheel contains only product code
- Cons: Every import is longer; Makefile and docs paths change once

### Option B: rename only `platform` to `kernel`
- Pros: Smallest change
- Cons: Leaves `app`, `worker`, `quality`, `synthetic` and others as collision-prone top-level names
- Why rejected: Fixes one collision, not the class of problem

### Option C: keep the flat layout and control `sys.path` ordering
- Pros: No renames
- Cons: Fragile; differs between pytest, uvicorn, Temporal workers and editors
- Why rejected: Correctness would depend on invocation details

### Option D: tooling inside the product root as `abacus.tooling`
- Pros: One root package
- Cons: Ships test-data generators in the production image; still needs a forbidden-import contract
- Why rejected: Tooling has no business in the runtime artefact

## Consequences
**Positive**
- Imports are unambiguous for agents, tools and humans
- The shared kernel and the platform module can no longer be confused

**Negative / costs accepted**
- Longer import paths
- Protected-path lists in three places (hook, CODEOWNERS, protected-paths.md) had to move together

**Follow-up work created**
- None beyond TASK-001, which moves every reference

## Enforcement
- [x] Lint rule: banned pattern `LAYOUT-001` fails on any entry under `backend/src/` other than `abacus/` and `abacus_tools/`; `BOUND-001` allows cross-module imports only through `abacus.modules.<m>.api`
- [x] Architecture / dependency rule in CI: import-linter layers contract (above) and forbidden contract `abacus` → `abacus_tools` (the only enforcement of that direction; ruff's banned-api cannot exempt `abacus_tools` itself and the tests that import it)
- [x] Hook or protected path: `.claude/hooks/_protected.py`, `.github/CODEOWNERS` and `docs/architecture/protected-paths.md` name the `abacus` paths
- [x] Packaging: the hatch wheel target includes only `src/abacus`

## Guidance for agents
Import product code from `abacus`, never from a bare top-level name. Shared infrastructure comes from `abacus.kernel`; anything that is a business capability belongs in a module.

**Do**
```python
from abacus.kernel.uow import unit_of_work
from abacus.modules.evidence.api import add_version
```

**Don't**
```python
from platform.uow import unit_of_work          # stdlib collision; old layout
from abacus.modules.platform import uow        # the platform module is not the kernel
from abacus_tools.synthetic import company     # inside abacus/ — product never imports tooling
```

## Revisit when
The backend is split into more than one deployable.

## Related
- ADRs: ADR-008, ADR-009, ADR-010 (superseded; decisions restated above), ADR-047, ADR-082, ADR-085, ADR-097
- Specs: SPEC-000
- Docs: `docs/architecture/protected-paths.md`, `docs/product/glossary.md` (Kernel)
