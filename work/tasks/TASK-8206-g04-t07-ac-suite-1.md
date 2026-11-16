---
id: TASK-8206
title: "G-04-T07: ADR-078 AC suite 1 for the red work (support sessions v2, admission hook, migration constraints, agent and portal denial)"
spec: SPEC-681
acceptance_criteria: [AC-14, AC-15, AC-16, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25]
risk_zone: red
status: in-review
branch: g04-t07-ac-suite-1
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-15
updated: 2026-11-15
plan_key: G-04-T07
---

## Objective
The independent AC suite for SPEC-681 and the G-04 red rules, written from the specs.

## Progress log
- `2026-11-15` — Written (DEC-5207). AC-37 asserts the stub state until G-04-T08.
- `2026-11-15` — Lane end pass green on the stack tip (#2080): `schema_check` (migrations up,
  down to base, up; RLS everywhere), the targeted suites (permission matrix, route
  introspection, app gates, tenant isolation, catalogues, status vocabulary, schema_check_db,
  G-02 support tests, the T07 AC suite) and `make check-fast`. Fixes in 5c0ad032d and
  819cffc82: audit refs carry identifiers only; staff routes in the route checker; reviewed
  lists extended; unique schema names (FirmPlanOut, StatusIncident*, ConsolePublication*,
  PlatformRegion*); web fixtures carry the v2 session fields.
