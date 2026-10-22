---
id: TASK-431
title: C5 v1.1 portal-half stub - portal identity and home models, home and preferences routes, contact unlock and MFA reset, /v1/me portal and mfa fields, matrix rows, flags portal.sign_in_v2 and portal.home_v2, contract doc, SPEC outline (P-08-T01)
spec: SPEC-320
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: red
status: done
epic: P-08
plan_key: P-08-T01
branch: p08-t01-portal-identity-stub
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The stub merges dark ... with generated client types, both flags off, and the start, renew and preview stubs answering one identical shape for any input." The start, renew and preview shapes are fixed (one model each for every input) but not served: see DEC-139.

## Plan (red zone)
- **Files:** `portal/contract.py` (home, preferences, the branding shape) and `portal/api.py` (ROUTERS); `identity/portal_contract.py` (unlock, MFA reset, the `/v1/me` portal and mfa models, the pre-session shapes) and `identity/api.py` (ROUTERS); `identity/routes.py` (`MeOut` two optional fields); `permission-matrix/portal.yaml` (new) and `identity.yaml`; `feature-flags/identity.yaml` and `portal.yaml` (new); generated files through `make regenerate`; `docs/contracts/portal-identity.md`, `README.md` register row, `c5-requests-binders.md` change log; SPEC-320; DEC-139.
- **Not touched:** `abacus/api/public_routes.py` and `app.py` (ADR-152's protected list; DEC-139). No error class (codes reserved in the contract doc; `error-codes.yaml` unchanged).
- **Migrations:** none (P-08-T05, T10, T17, T18, T21 own them).
- **Tests:** `backend/tests/contracts/c5_portal/test_c5_portal_stub.py` (AC-1 to AC-5); test lists: `tests/unit/api/test_app_gates.py` (two POSTs that return state), `test_preregistration.py` (portal now landed), `tests/acceptance/test_f03_status_vocabulary.py` (two card `state` fields are not object statuses; `portal_status` belongs to `invitation`); generated matrix and route tests.
- **Rollback:** revert the commit; both flags are off and nothing reads the new routes; `/v1/me` fields are optional and null.

## What changed
- **Routes:** `GET /v1/portal/home?scope_id=` (`portal_home.read`, `scope_only`), `PUT /v1/portal/preferences` (`portal_preferences.update`; 409 documented) behind `portal.home_v2`; `POST /v1/clients/{client_id}/contacts/{contact_id}/portal-unlock` (`contact.unlock`) and `/mfa-reset` + Idempotency-Key (`contact.mfa_reset`, fresh MFA) behind `portal.sign_in_v2`. Off 404, on 501.
- **`/v1/me`:** optional `portal` (`MePortalOut`: shell, scopes, nav, landing) and `mfa` (`MeMfaOut`), null until P-08-T07 and T17.
- **Not served (DEC-139):** branding, logo, `/v1/portal/auth/*`, `/v1/portal/links/renew`, `/v1/invitations/preview`, accept v2: shapes in code, unrouted, classified and tested.
- **Matrix:** `portal_home.read`, `portal_preferences.update` (client admin and contributor; agent and system deny); `contact.unlock` (firm admin, security admin, partner, manager, client service; agent and system deny); `contact.mfa_reset` (security admin, fresh MFA; agent and system deny).
- **Flags:** `portal.sign_in_v2` (owner notanaskhan), `portal.home_v2` (owner ayushkbhatia); boolean, default false, created 2026-10-23, expire 2027-01-21.
- **Generated:** `_matrix.py`, `_flags.py`, `actions.gen.ts`, generated matrix and route tests, `openapi.json` and the api-client (new types only; no `abacus__` schema added, operation ids unique).

## Progress log
- 2026-10-23: built on `origin/main` at 36b20f6. `make regenerate`, `make generate`, `make check-generated` clean. `tests/contracts/c5_portal` and the named unit, acceptance and security suites green. ruff, pyright clean on touched files.
