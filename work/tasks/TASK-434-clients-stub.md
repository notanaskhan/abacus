---
id: TASK-434
title: Clients family contract stub v1 (organisations) - classified models, 501 routes for the clients index, record, overview, PATCH, relationships and TIN reveal, matrix rows, clients.v2 flag, import ban, contract doc (P-07-T04)
spec: SPEC-321
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T04
branch: p07-t04-clients-stub
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The stub merges dark in the Thu Dec 17 train and no schema field carries a TIN, a hidden-by-wall count or a walled client name." (Solo edition: merged when green.)

## Plan (red zone)
- **Files:** `organisations/contract.py` (models and 501 stubs), `organisations/api.py` (ROUTERS), `permission-matrix/organisations.yaml` (new; `client.read` moved from `engagements.yaml`), `feature-flags/organisations.yaml` (new), `backend/pyproject.toml` (import-linter contract), generated files through `make regenerate`, `docs/architecture/error-codes.yaml` (`stale_version`), `docs/contracts/clients.md`, `docs/contracts/README.md`, SPEC-321 outline, DEC-141, `tests/unit/api/test_app_gates.py` (the reveal is a non-creating POST).
- **Migrations:** none (P-07-T07 owns the TIN migration).
- **Tests:** `backend/tests/contracts/clients/test_clients_stub.py` (AC-1 to AC-5); the generated matrix and route-introspection tests cover the new rows and routes.
- **Rollback:** revert the commit; nothing reads the new routes and the flag is off. `client.read` widening also reverts.

## What changed
- **Routes (404 with `clients.v2` off, 501 on; no fixtures):** `GET /v1/clients` (`client.read`, `ListPage[ClientRowOut]`), `GET /v1/clients/{id}` (`client.read`, `ClientRecordOut`), `GET /v1/clients/{id}/overview` (`client.read`), `PATCH /v1/clients/{id}` (`client.update`, 409 `stale_version` / `illegal_transition`), `GET /v1/clients/{id}/relationships` (`client.read`), `POST /v1/client-entities/{id}/tin/reveal` (`tin.reveal`).
- **Matrix:** `client.read` every firm role, agent/system deny; `client.update` firm_admin + firm_partner, agent/system deny; `tin.reveal` engagement partner, manager, EQR reviewer + `mfa_recent`, reason, agent/system deny; `not_offshore`, the preparer path, the manager path on `client.update` and `firm_partner` on `client.read` land with the live routes (DEC-141).
- **Flag:** `clients.v2` (boolean, default false, owner notanaskhan, created 2026-10-23, expires 2027-04-21, `override: DEC-137`).
- **Import ban:** `organisations` never imports `abacus.ai_gateway` or `abacus.modules.agents` directly.
- **Error code:** `stale_version` (409).

## Progress log
- 2026-10-23: built on origin/main at acda5f2. `make regenerate`, `make generate`, `make check-generated` clean; no new `abacus__`-prefixed schema; `tests/contracts/clients` 15 passed; `tests/unit/api`, `test_independence`, `test_classification`, `test_f03_status_vocabulary`, `test_permission_matrix_generated`, `test_route_introspection` 4328 passed. A nullable `status` on the PATCH body failed F-03-T10's "every status field is an enum" check (an `anyOf`), so the change is nested as `status_change` (DEC-141) rather than editing the test. `tests/unit/tools/test_feature_flag_override.py` (F-03-T37) refuses any flag expiring before Feb 1, 2027, so `clients.v2` carries DEC-137's override to 2027-04-21. `tests/unit/identity/test_permission_matrix.py` drives every allowed cell through `authorise` without member facts: `not_offshore` denies at the condition layer and `firm_partner` on a read looks up the member's level in the database, so both wait for the live routes (DEC-141).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-141 | conditions only narrow; reveal reasons; the one plain-TIN payload; nested status change | no |
