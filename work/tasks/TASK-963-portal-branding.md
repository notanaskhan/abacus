---
id: TASK-963
title: Portal branding and host resolution — migration 0111, definer lookups, GET /v1/portal/branding and /branding/logo, logo re-encode (P-08-T05)
spec: SPEC-320
acceptance_criteria: [AC-2, AC-5]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T05
branch: s5-portal-branding
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Known and unknown hosts get the same response shape, the payload holds Public fields only, and the logo is served same-origin after server-side re-encoding."

## Plan (red zone)
- **Migration:** `0111_portal_branding.py` — `portal_branding` and `portal_preferences` (forced RLS, column grants), global `portal_domains` (no app grant), definers `portal_resolve_host`, `portal_host_logo`, `portal_domain_add`, `portal_domain_activate`. Rollback: `alembic downgrade 0110`.
- **Registries:** `portal/registry.py`; schema_check GLOBAL_TABLES, NON_TENANT_TABLES and DEFINER_FUNCTIONS, with their expectations in `test_schema_check_db.py`.
- **Routes:** `PORTAL_PUBLIC` marker in `identity/routing.py` (two paths only), on ROUTE-001's exception list; ADR-152 lists both paths.
- **Code:** `portal/branding.py` (host hint, neutral answer, isolated logo re-encode, writers), `portal/repository.py`, routes in `portal/contract.py`.
- **Tests:** `tests/integration/test_portal_branding.py` (same keys for known, unknown, malformed and unverified hosts; no tenant id; no "accrued"; PNG out, metadata dropped, 512 px; non-images refused; logo needs branding); route marker tests in `test_routing.py`; C5 stub list updated.

## Progress log
- 2026-10-23: built. Two deviations recorded in DEC-154 (logo stored in the row; `portal_domains` global). Postgres caps a regex repetition at 255, so URL lengths are separate checks.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-154 | logo storage, global hosts, route marker | no (ADR-152 updated while proposed) |
