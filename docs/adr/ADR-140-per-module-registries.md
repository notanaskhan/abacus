---
id: ADR-140
title: Registries and the permission matrix are split per module
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: amber
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
Single protected files are the main merge hotspot: `TABLE_OWNERS`, `INSERT_ONLY_TABLES`, `APP_INSERT_COLUMNS` and `DEFINER_FUNCTIONS` in `schema_check.py`; `MODULE_DEPENDENCIES`; `ROUTERS` in `abacus/api/app.py`; `MODULES` in `abacus/worker/__main__.py`; `permission-matrix.yaml`; and `feature-flags.yaml`. With 29 modules (ADR-137), every feature branch edits the same files, and branches collide.

## Decision
1. Each module declares its own registrations in `modules/<m>/registry.py`: its tables, insert-only tables, routers, workflows, subscriptions and matrix actions.
2. The quality gate and the app and worker boot **collect** these files. A static check verifies that every module appears once in a single sorted `MODULES` tuple.
3. The permission matrix is split into `docs/architecture/permission-matrix/<module>.yaml` and compiled into one artefact (`_matrix.py`). Flags are split per module the same way. The compiled matrix stays protected, and generated allow and deny tests still cover every action.
4. **One pre-registration PR per wave** creates the registrations, empty packages and matrix sections for the modules that wave needs, so feature PRs rarely touch shared files. The first one covers all 16 new modules.

## Options considered
### Option A: per-module registry files, compiled — chosen
- Pros: feature branches touch their own module's files; the single-artefact check is kept.
- Cons: a compile step; a collector to maintain.

### Option B: keep single protected files
- Pros: nothing to build.
- Cons: constant conflicts on the same lines.
- Why rejected: the main merge hotspot.

## Consequences
**Positive**
- Fewer collisions; ownership is local to the module.

**Negative / costs accepted**
- A reader must look at several files to see the whole picture; the compiled artefact is the single view.

**Follow-up work created**
- **Code:** per-module `registry.py`, collectors in `schema_check`, app and worker boot, and the matrix compiler. Epic EP-01, S1 (DEC-13).
- **Specs:** none beyond updating the quality-gate description. EP-01, S1.
- **Glossary:** none.
- **Matrix:** move existing rows into per-module files without changing any decision. EP-01, S1.
- **Registry:** the S1 pre-registration PR, then one per wave. EP-01, S1 onward. (docs/plan/03-backend-architecture.md section 2.5 says Sprint 0; DEC-13 says S1, and S1 is used here.)

## Enforcement
- [ ] Test: compiling the per-module matrix gives the same decisions as the old single file (byte-for-byte on the first split).
- [ ] `schema_check`: every table is owned by exactly one module's registry, and every entry exists (ADR-103 rule kept).
- [ ] Static check: `MODULES` is sorted and lists each module once.
- [ ] Generated allow and deny tests (ADR-027) run on the compiled matrix.

## Guidance for agents
Add a table, route or action in your module's registry and matrix file. Do not edit another module's registry. Run `make generate` after a matrix change.

**Do**
```
# modules/requests/registry.py
TABLES = {"request_items": "requests"}
```

**Don't**
```
# schema_check.py
TABLE_OWNERS["request_items"] = "requests"   # the old single map
```

## Revisit when
The compile step becomes slow, or a registry needs a cross-module value that per-module files cannot express.

## Related
- P-ID: P-39 in docs/plan/09-decisions-adrs.md section 9.4; DEC-13.
- Amends: ADR-103 Decision (ownership declared in the single `TABLE_OWNERS` map; now each module declares its tables and `schema_check` collects them; the one-owner-per-table rule stands). ADR-027 file layout (`docs/architecture/permission-matrix.yaml` becomes per-module files compiled into one artefact; the policy model stands).
- Related ADRs: ADR-137, ADR-106.
- Docs: docs/plan/03-backend-architecture.md section 2.5.
