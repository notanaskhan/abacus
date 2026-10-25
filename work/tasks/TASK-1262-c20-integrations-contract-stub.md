---
id: TASK-1262
title: C20 v1 contract stub - POR-16 family and the integrations framework port and write-capability registry schema; docs/contracts/c20-integrations.md v1 (A-02-T06)
spec: SPEC-333
acceptance_criteria: [AC-35, AC-36, AC-38, AC-49]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T06
branch: s9a-contract-stubs
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Every route answers 501 under its matrix action, an empty registry validates against the
schema, and fixture mode serves POR-16a-g from typed fixtures" (A-02-T06).

## Plan (red zone: contract)
- **Module** `modules/integrations/` is pre-registered (F-03-T08, ADR-140: `api.py`,
  `registry.py`, README). DEC-13's module-map rule: other modules import only `api.py`; the stub
  imports only the kernel and `identity.api`, so no new import edge is needed (the
  `integrations -> connections` edge is the implementation's, T16).
- **Routes** `integrations/contract.py` (new), behind the new flag `connections.portal_v2`
  (404 off, 501 on): `GET /v1/portal/entities/{entity_id}/connections` (`connection.read`),
  `POST …/connections/{catalog_key}/start` (`connection.create`, fresh MFA, Idempotency-Key),
  `GET /v1/portal/connections/{id}` (`connection.read`), `POST …/{id}/retry`
  (`connection.retry`, Idempotency-Key), `POST …/{id}/disconnect` (`connection.revoke`,
  Idempotency-Key), `POST /v1/connections/{id}/reconnect-requests`
  (`connection.reconnect_request`, Idempotency-Key, 201), `POST
  /v1/engagements/{id}/connection/pulls` (`ledger.pull`, Idempotency-Key, 202). Matrix rows exist
  (A-02-T02, TASK-1185).
- **Ports and schema** `integrations/ports.py` (new): the `IntegrationAdapter` protocol and the
  `WriteCapabilityRegistry` Pydantic schema (read connectors with egress hosts; writes reserved,
  none enabled); exported from `integrations/api.py` with `ROUTERS`.
- **Status words**: `integration.available` gains `client_label: "Not connected"` (POR-16a).
- **Fixtures** (TS): `seed/connections.ts`, `handlers/connections.ts`, `scenarios/POR-16.ts`
  (a-g; DF-19 masks the posting copy).
- **Contract doc** `docs/contracts/c20-integrations.md` v1 and its register row.
- **Tests** `backend/tests/contracts/c20_integrations/test_c20_stub.py` (provider).
- **Rollback**: revert and `make regenerate`; no migration.

## Progress log
- 2026-10-26: built. `tests/contracts/c20_integrations/test_c20_stub.py` 31 passed; app gates,
  route introspection and the status-vocabulary acceptance suite pass (the two sync-run status
  fields join NO_YAML_ENTRY beside RetrievalOut, the same `failed_validation` gap); vitest
  fixtures 474 passed; tsc and eslint clean. Two flags rather than one: the pull is behind
  `connections.live_ledger` as A-02 §4.3 says. DEC-377.
- Not here: the fail-closed adapter registry and catalogue (T12), the registry file and compiler
  (T15), POR-16 screens (T18).
