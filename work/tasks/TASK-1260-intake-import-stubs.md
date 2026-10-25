---
id: TASK-1260
title: Intake and import contract stubs (P-07-T37)
spec: SPEC-332
acceptance_criteria: [AC-23]
risk_zone: red
status: in-review
epic: P-07
plan_key: P-07-T37
branch: s9a-engagement-lifecycle
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The stubs merge in the S9 batch with Idempotency-Key required on commit and run." CLI-06's
single intake (P-07-T42) and bulk import (P-07-T52) start from these stubs.

## Plan (red zone)
- **Stub** `engagements/intake_contract.py` (new; P-07 §4.1 puts intake and import in
  `engagements`): classified models and routes, each one matrix action:
  - `POST /v1/clients/dedupe` (`client.create`; names in the body, never the URL).
  - `POST /v1/client-intake-drafts`, `GET/PATCH/DELETE …/{draft_id}`, `POST …/{draft_id}/validate`
    (`client.intake`); `POST …/{draft_id}/commit` (`client.intake`, `{start_acceptance}`,
    `Idempotency-Key` required).
  - `POST /v1/client-imports` (multipart upload), `GET …/{import_id}`, `GET …/{import_id}/rows`,
    `PUT …/{import_id}/rows/{row_id}/decision`, `POST …/{import_id}/run` (202, `Idempotency-Key`
    required) (`client_import.run`).
- **Behaviour** (the DEC-326 order): client principal, agent or system 403 first; authorise the
  action firm-level; flag `clients.intake_v2` (new, default off) off 404; on 501
  `not_implemented` until P-07-T42 (intake) and P-07-T52 (import). The `Idempotency-Key` header
  is a required parameter on commit and run (422 without it, before the stub answers).
- **Models**: no TIN in any schema: import rows carry `MaskedTinOut`-style masked shapes
  (kind, last four); no hidden-by-wall field or count; statuses that are not registry statuses
  are not named `status` (the import's state is C2 `client_import` if registered, else a code).
- **Matrix**: `client_import.run` (new: firm admin, `firm_partner`, `firm_manager`; agent and
  system deny); `client.intake` (exists; the manager cell lands with TASK-1259). `client.create`
  exists.
- **Contract doc** `docs/contracts/intake-import.md` (new) and the register row in
  `docs/contracts/README.md`; `make generate`.
- **Tests**: `tests/contracts/intake_import/test_intake_import_stub.py` (each route's action,
  404 flag off / 501 on, the order of checks, Idempotency-Key required on commit and run, no TIN
  or wall field, agent and system denied).
- **Rollback**: revert the commit.

## Progress log
- 2026-10-26: planned.
