---
id: TASK-313
title: "F-03-T07: per-module registries (ADR-140) — tables, routers and worker parts collected; matrix and flags split per module"
spec: SPEC-306
acceptance_criteria: [AC-1]
risk_zone: red
status: done
branch: task-313-registries
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan (ADR-140, P-39)
- `abacus.modules.MODULES`: one sorted tuple of the module names. A test keeps it unique, sorted and equal to the packages on disk.
- `modules/<m>/registry.py` (data only): `TABLES`, `INSERT_ONLY`, `INSERT_COLUMNS` and `UPDATE_COLUMNS`. They were generated from schema_check's maps with their comments kept.
  - `schema_check` collects them and keeps only the platform's own (migrations, kernel, ai_gateway, eval tooling).
  - A table claimed twice fails.
- Routers: each `api.py` declares `ROUTERS`, and `api/app.py` mounts them in MODULES order (same 25 routers).
- Worker: it hosts every module whose `api.py` has `SUBSCRIPTIONS` (the same 6, now in MODULES order), with their `WORKFLOWS` and `ACTIVITIES`.
- Matrix: `docs/architecture/permission-matrix/_roles.yaml` plus one file per module.
  - `codegen.permission_matrix.source()` joins them; actions render sorted.
  - The decisions are identical to the old single file (verified); only the order changed, once.
  - An action in two files fails as a duplicate key.
- Flags: `docs/architecture/feature-flags/<module>.yaml`, joined the same way; FLAGS are identical.
- BOUND-001 allows `abacus.modules.MODULES` (names only).
- Docs updated: AGENTS.md, identity and kernel READMEs, the api-contract skill, the security reviewer.

## Deviation from ADR-140, recorded
- ADR-140 has `registry.py` declare routers, workflows and subscriptions too. Here those stay in each module's `api.py`, so the quality gate loads registries without importing product code (routes, Temporal); the collectors read both files.

## Definition of done
- [x] Unit suite passes.
- [x] schema_check passes on the collected registries.
- [x] Matrix and flags compile to the same decisions.
- [x] check-fast passes.
