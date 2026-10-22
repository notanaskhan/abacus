---
id: TASK-471
title: Engagements family contract stub v2 (C1 v1.1 note) - index envelope with tiles and service-line facets, record projection, gates, interim recorded letter, engagement-type catalogue, drafts, start-acceptance and create; matrix; engagements.v2 flag; contract doc (P-07-T05)
spec: SPEC-321
acceptance_criteria: [AC-10, AC-11, AC-12, AC-13, AC-14, AC-15]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T05
branch: p07-t05-engagements-stub
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The generated client exposes every operation as 501 behind the flag and the catalogue fixture contains no single_audit entry."

## Plan (red zone)
- **Files:** `engagements/contract.py` (models, error codes, 501 stubs), `engagements/api.py` (ROUTERS, v2 routers first), `permission-matrix/engagements.yaml` (`engagement.create`, `letter.record` deny agent and system) and `organisations.yaml` (`client.intake`), `feature-flags/engagements.yaml` (`engagements.v2`), generated files through `make regenerate`, `error-codes.yaml`, `docs/contracts/engagements-v2.md`, the C1 v1.1 note in `work-items.md`, the register row, SPEC-321 Stories 3 and 4, DEC-143, `tests/unit/api/test_app_gates.py`.
- **Migrations:** none (P-07-T16 owns `engagement_drafts`).
- **Tests:** `backend/tests/contracts/engagements_v2/test_engagements_v2_stub.py` (AC-10 to AC-15), including the route-order guard for `/index`.
- **Rollback:** revert the commit; the flag is off and the live routes are untouched.

## What changed
- **Routes (404 with `engagements.v2` off, 501 on):** `GET /v1/engagements/index` (`EngagementIndexPage`), `GET /v1/engagements/{id}/record`, `GET /v1/engagements/{id}/gates` (`engagement.read_metadata`); `PUT /v1/engagements/{id}/letter/record` (`letter.record`); `GET /v1/engagement-types`, `POST /v1/engagement-drafts` (201), `GET`/`PATCH`/`DELETE /v1/engagement-drafts/{id}`, `POST …/validate`, `POST …/create` (201, `Idempotency-Key`) (`engagement.create`); `POST …/start-acceptance` (201, `client.intake`).
- **Matrix:** new `client.intake` (firm admin, `firm_partner`; agent and system deny); `engagement.create` and `letter.record` gain agent and system deny. DEC-38's cells and `gates_met(G1)` land with the live routes (DEC-143).
- **Flag:** `engagements.v2` (boolean, default false, owner notanaskhan, created 2026-10-23, expires 2027-04-21, `override: DEC-137`).
- **Error codes:** `unknown_engagement_type` (422), `letter_before_acceptance`, `gate_unmet` (409); `stale_version` gains a raiser.

## Progress log
- 2026-10-23: built on origin/main at 12dc051. `make regenerate`, `make check-generated` clean; no new `abacus__`-prefixed schema; operation ids unique. `tests/contracts/engagements_v2` 24 passed; the api, identity, classification, status-vocabulary, generated-matrix and route-introspection suites pass except two `portal_home.read` cases from P-08-T01 already on main. `errors=(422, …)` is not an AbacusRouter option (422 is always documented), so the drafts routes declare 409 and 501 only. TASK-434 (P-07-T04) was renumbered TASK-470 here, because another session merged a TASK-434 at the same time.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-143 | paths beside the live routes; OQ-2 `client.intake`; deferred cells; catalogue enum | no |
