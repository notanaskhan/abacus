---
id: TASK-8203
title: "G-04-T04: expand-only platform migration 0920 (plan entitlements, usage alerts, plan requests, support, help, status, regions, directory, platform log)"
spec: SPEC-680
acceptance_criteria: [AC-35, AC-41, AC-46, AC-52]
risk_zone: red
status: in-review
branch: g04-t04-platform-migration
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-15
updated: 2026-11-15
plan_key: G-04-T04
---

## Objective
G-04 migration A (epic §4.2): every table, constraint, grant, trigger and definer the console,
plan & usage and support services need, expand only.

## Plan (red)
1. `0920_platform_console_plan_support.py` on 0901: 8 tenant tables, 8 global, 9 readers,
   7 owner-only writers, 6 trigger functions; widen `tenant_entitlements.module`.
2. **Protected** `abacus_tools/quality/schema_check.py` registrations; `platform/registry.py`.
3. Tests at the end pass: up/down/up, `schema_check`, the AC-35 uniqueness, AC-41 CHECK, AC-52
   freeze (G-04-T07 suite).
Rollback: `alembic downgrade 0901` (drops only what 0920 created; deletes service-line rows).

## Progress log
- `2026-11-15` — Built (DEC-5204). Lint clean. Migration run, schema_check and AC tests at the
  lane's end pass under the test lock.
