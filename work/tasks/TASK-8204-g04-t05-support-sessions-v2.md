---
id: TASK-8204
title: "G-04-T05: SPEC-012 amendment in identity (SPEC-681): firm-only approval, one-object scope, Decline, 120 minutes, US attestation, emergency route removed"
spec: SPEC-681
acceptance_criteria: [AC-14, AC-15, AC-16, AC-17, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25]
risk_zone: red
status: in-review
branch: g04-t05-support-sessions-v2
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-15
updated: 2026-11-15
plan_key: G-04-T05
---

## Objective
SPEC-681 in the identity module: the data, the service, the routes, the scope narrowing, the
staff-token claims and the notifications.

## Plan (red, protected paths)
1. Migration 0921 (support_sessions v2 with NOT VALID CHECKs; firms tenant code and onboarding).
2. `identity/support.py`: remove `emergency_approve`; request v2; approver role; `decline_session`;
   TRI and scope-label hooks; `support_context` carries the scope.
3. `identity/authz/__init__.py`: `in_support_scope` in `authorise` (layer `support_scope`, 404 in
   `api/app.py`) and in `visible()` / `visible_scope()`.
4. `identity/routes.py`: drop the staff approve route; v2 request body; decline route; v2 fields.
5. `identity/tokens.py`: `platform_roles`, `us_located` claims. `notifications/catalogue.py`.
6. `platform/api.py` registers the TRI check; `platform/entitlements.py` service-line modules.
7. Tests: T07's AC suite; existing tests moved to the new contract.
Rollback: revert the code; `alembic downgrade 0920` (deletes declined rows, maps
integration-settings sessions to metadata and security_admin approvals to firm_admin).

## Progress log
- `2026-11-15` — Built (DEC-5205). Imports clean, client regenerated. Integration tests and the
  security review at the lane's end pass.
- `2026-11-15` — Lane end pass green on the stack tip (#2080): `schema_check` (migrations up,
  down to base, up; RLS everywhere), the targeted suites (permission matrix, route
  introspection, app gates, tenant isolation, catalogues, status vocabulary, schema_check_db,
  G-02 support tests, the T07 AC suite) and `make check-fast`. Fixes in 5c0ad032d and
  819cffc82: audit refs carry identifiers only; staff routes in the route checker; reviewed
  lists extended; unique schema names (FirmPlanOut, StatusIncident*, ConsolePublication*,
  PlatformRegion*); web fixtures carry the v2 session fields.
