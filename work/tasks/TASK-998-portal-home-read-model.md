---
id: TASK-998
title: Client stage projection and the portal home read model — stages.py, home.py, home_sources, preferences, migration 0115 (P-08-T12, P-08-T13)
spec: SPEC-320
acceptance_criteria: [AC-15, AC-16, AC-17]
risk_zone: amber
status: in-progress
epic: P-08
plan_key: P-08-T12; P-08-T13
branch: s6-portal-signin
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Every registry code of the four work-item kinds maps to one stage, and no firm status word can be returned" (T12). "Claire's home returns Upload 2 documents and binder 19 of 21 from the E0 load, and a request for another client's scope answers 404" (T13).

## Plan (amber zone)
- **Code:** `portal/codes.py` (the client code Literals, moved out of `contract.py` so the read model imports no routes); `portal/stages.py` (DEC-209); `portal/home.py` and `portal/home_sources/{__init__,requests,engagements}.py` (DEC-210); routes in `portal/contract.py` go live behind `portal.home_v2`.
- **Module reads:** `engagements.api.portal_work_items` (through `visible_scope(..., "portal_scope")`), `requests.api.client_home` (repository `client_home_items` through `visible_items`), `identity.api.scope_facts` and `FULL_ROLES`.
- **Migration:** `0115_portal_preferences_scopes.py` widens the `scope_kind` check to the grant scope kinds. Rollback: `alembic downgrade 0114`.
- **Tests:** `tests/unit/portal/test_stages.py` (exhaustiveness over the generated enums, golden rows); `tests/integration/test_portal_home.py` (AC-15 to AC-17); the C5 stub test treats the two routes as live.

## Progress log
- 2026-10-23: T12 and T13 built; 66 unit and 4 integration tests pass. Found that a client-wide or work-item grant derives no engagement role, so `authorise` and `visible()` see nothing for a household `taxpayer` grant (DEC-129 says a client-wide grant covers its client's engagements). The home tests use engagement-scope `owner` grants, the shape E0 seeds today. Claire's E0 figures (Upload 2, 19 of 21, 37 sorted) wait for P-08-T14's slice.

- 2026-10-23: DEC-211 fixes the client-wide grant gap in `identity.repository` (`client_grant_engagements`, `engagement_role`) with `engagements.engagements_of_scope` registered; `tests/integration/test_client_wide_grants.py` (11 cases). Red: identity authorisation.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-209 | The stage table leaves signing, entity returns and SOC 2 unmapped | No |
| DEC-210 | First visit, tax cards and the sorted count are not defined by the plan | No |
| DEC-211 | DEC-129's client-wide coverage was missing from role derivation | No (DEC-129, ADR-146) |
