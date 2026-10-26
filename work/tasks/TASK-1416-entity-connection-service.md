---
id: TASK-1416
title: Entity-scoped connection service and POR-16 routes (A-02-T16)
spec: SPEC-333
acceptance_criteria: [AC-35, AC-36, AC-37, AC-39, AC-40, AC-41, AC-42]
risk_zone: red
status: in-progress
epic: A-02
plan_key: A-02-T16
branch: s11-integrations
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Starting without the authorization is refused authorization_required, a reused OAuth state is
refused, and the audit log renders Connected by Tess Moreno (client)."

## Plan
- Migration `0215_connection_state_consent.py` (down 0197): `connection_states.consent_id` (FK
  on tenant, entity and consent to `connection_consents`, so a state carries only a consent on
  its own entity) with its INSERT grant; `connection_states.connection_id` NULL (the connection a
  reconnect re-authorises, same entity).
- `connections/entity.py` (service): entity-scoped facts and actions. Authorisation is per
  engagement of the entity (`connection.read`, `.create`, `.retry`, `.disconnect`; walls,
  independence, `scope_only`, fresh MFA from the matrix): the first engagement of the entity the
  person may act on, else 404 (INV-4). `entity_connections` (live connections, last failed run,
  open reconnect request, who connected), `start_entity` (consent row as shown + hashed state
  bound to tenant, person, entity, consent; audited `connection.consent_recorded` and
  `connection.started`), `complete_entity` (state spent once in its own unit of work; reused,
  expired, someone else's: `invalid_state`; a reconnect re-authorises in place, audited
  `connection.reauthorized`; a new one `connection.created`; the consent link written once;
  open reconnect requests fulfilled), `connection_detail` (last 5 runs, activity lines),
  `retry` (one run; a running one is returned), `disconnect` (`seen_version`, secret
  crypto-erased, status `revoked`, received data kept, `connection.revoked`).
- Actor grammar: every connection event carries `client_actor=1` when a client acted; the
  details drawer's activity reads "Connected by Tess Moreno (client)", "Reconnected by …",
  "Disconnected by …".
- Legacy engagement routes (`/v1/engagements/{id}/connection/*`, `/v1/connections/complete`)
  stay, reading the entity's live ledger (bank feeds may now sit beside it) and completing a
  portal-started state through the entity path.
- `integrations/client_connect.py`: POR-16 cards composed from the honest catalogue and the
  entity's connections, the start's catalogue checks (`connector_not_available`,
  `consent_version_stale`, `ledger_already_connected`, `authorization_required`); the C20
  stubs in `integrations/contract.py` become live behind `connections.portal_v2`.
- Module edge `integrations -> connections` (A-02 §4.1) in MODULE_DEPENDENCIES.
- Tests: `tests/integration/test_a02t16_entity_connections.py` (ACs), C20 stub test updates.
- Rollback: flag off; downgrade drops the two columns.

## Progress log
- 2026-10-27: plan written.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
