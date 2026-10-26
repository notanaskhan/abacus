---
id: TASK-1332
title: Security-center contract stub (ADM-06 family) - classified models, 501 routes behind security_center.v1, fixtures, docs/contracts/security-center.md v1
spec: SPEC-349
acceptance_criteria: [AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T11
branch: s10b-audit-trail-export
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Contract first for ADM-06 (G-02-T11): the shapes, routes, flag gate and fixtures of the security
center, so the independent AC suite (T12, TASK-1333) and the screen (T16) build against them
before sign-in policy and sessions (T14), the incident register's depth (T18), the export
schedule (T19) and the safeguards program (T20) exist.

## Plan
- **Module placement (DEC-432).** Each stub lives in the module that will implement it, because
  identity may import no other module (`MODULE_DEPENDENCIES["identity"]` is empty), so routes in
  identity could never call platform's incident or safeguards service or evidence's schedule:
  - `identity/security_center_contract.py`: `GET /v1/firm/security` (overview: sign-in, MFA
    summary, portal floor, residency, support switch, the viewer's actions), `PUT …/sign-in`,
    `PUT …/portal-sign-in`, `PUT …/sso-exempt-account`, `GET …/sessions`,
    `POST …/sessions/{session_id}/sign-out`, `GET …/posture`, `POST /v1/firm/staff/{user_id}/unlock`,
    `GET`/`PUT /v1/firm/support-access`.
  - `platform/security_center_contract.py`: the incident read side and decisions beside Q-02's
    create route (`GET /v1/firm/security/incidents`, `GET …/{incident_id}`,
    `POST …/{incident_id}/timeline`, `POST …/{incident_id}/decisions`) and the safeguards program
    (`GET`/`PUT /v1/firm/safeguards`, `PUT …/controls/{control_key}`, `POST …/wisp-pack`).
  - `evidence/firm_export_schedule_contract.py`: `GET`/`PUT /v1/firm/data-exports/schedule`,
    `POST …/schedule/approve`, mounted **before** Q-02's firm-export router, whose
    `POST /{export_id}/approve` would otherwise match `schedule/approve`.
- Q-02 keeps what it owns: incident create (`POST /v1/firm/security/incidents`), the on-demand
  export and its history (`GET`/`POST /v1/firm/data-exports`, approve, decline, link), and the
  retention policies ADM-06 F reads (`GET /v1/retention/policies`). Nothing here duplicates them.
- **Gate (security review L1, as audit-log v1):** every route authorises first (client principal
  404; agent, system and anyone without the action 403, fresh MFA included), then reads
  `security_center.v1` (off 404, on 501 `not_implemented`).
- **One matrix action per route**, all from G-02-T02 (verified in `permission-matrix/*.yaml`):
  `security.read`, `security.manage`, `session.end`, `staff.unlock`, `support_session.read`,
  `support_session.manage`, `incident.read`, `incident.manage`, `incident.decide`,
  `firm_export.read`, `firm_export.schedule`, `firm_export.approve`. No matrix edit.
- **Error codes:** `sso_not_verified`, `policy_loosening_refused`, `stale_version`,
  `decider_must_differ`, `approver_must_differ`, `already_decided`, `support_requests_disabled`
  exist. One is added: `sso_exempt_needs_hardware_key` (409, AC-18) in
  `identity/governance_errors.py`, catalogue rebuilt with `error_codes --write`.
- `docs/contracts/security-center.md` v1 and its README row.
- Consumer contract test `backend/tests/contracts/security_center/test_security_center_contract.py`.
- Fixtures: `apps/web/src/fixtures/seed/security-center.ts`, `handlers/security-center.ts`,
  `scenarios/ADM-06.ts` (a to h, plus `sessions`, `unlock`, `support_requested`,
  `support_granted`, `support_declined`, `support_revoked`). The security-center types are local
  interfaces mirroring the Pydantic models field for field, because `make generate` runs at the
  integration step; incidents' Q-02 half, the on-demand export and the support sessions use the
  generated types that already exist.
- No migration, no flag or matrix edit. DEC-432 records the decisions.
- Rollback: revert; the flag stays off.

## Files
- New: `backend/src/abacus/modules/identity/security_center_contract.py`,
  `backend/src/abacus/modules/platform/security_center_contract.py`,
  `backend/src/abacus/modules/evidence/firm_export_schedule_contract.py`,
  `docs/contracts/security-center.md`,
  `backend/tests/contracts/security_center/{__init__.py,test_security_center_contract.py}`,
  `apps/web/src/fixtures/{seed,handlers}/security-center.ts`, `apps/web/src/fixtures/scenarios/ADM-06.ts`.
- Changed: `identity/api.py`, `platform/api.py`, `evidence/api.py` (ROUTERS),
  `identity/governance_errors.py`, `docs/architecture/error-codes.yaml` (generated),
  `docs/contracts/README.md` (row), `docs/product/decision-log.md` (DEC-432).

## Tests
- Contract: each route's one action, 404 and 501 declared, the family is exactly these routes,
  every field classified, request context and the pack link classified, no MFA-off or
  retention write path, the gate order (matrix before flag), the schedule path not shadowed.

## For the main session after `make generate`
- Switch `seed/security-center.ts` from its local interfaces to the generated types (same names:
  `SecurityOverviewOut`, `SignInPolicyOut`, …) and add the TS contract test against the OpenAPI
  document, as `contracts/audit-log.contract.test.ts` does.
- Regenerate the route-introspection security tests.

## Progress log
- 2026-10-26: built (not committed; the main session commits and runs `make generate`). Contract
  test 102 passed. Gates on touched files: ruff format/check, pyright, `lint-imports` (5 kept),
  `banned_patterns`, `error_codes` (`--write` for `sso_exempt_needs_hardware_key`),
  `validate_docs`; web `tsc` (no errors in `src/`; the 12 in `packages/api-client` are
  pre-existing), eslint, prettier. `tests/security/test_route_introspection.py` fails two tests
  until the route-introspection list is regenerated (21 new routes): expected, regenerate.
  `tests/contracts/compliance_kernel` green with the schedule mounted ahead of Q-02's router.
- 2026-10-26: the portal floor model was first named `PortalSignInPolicyOut`, which collides
  with `portal/contract.py`'s model of that name and renames both OpenAPI schemas to their long
  module paths; renamed to `PortalSignInFloorOut`/`PortalSignInFloorIn`. A broad `sed` for the
  rename touched `portal/contract.py` and two c5 tests by mistake; reverted the same minute (no
  diff remains). Lint idea: a contract test asserting no OpenAPI schema key starts with
  `abacus__` beyond the known list would catch the collision at the stub.
