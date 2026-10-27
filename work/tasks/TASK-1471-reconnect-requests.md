---
id: TASK-1471
title: Firm reconnect requests and the portal reconnect to-do (A-02-T23)
spec: SPEC-333
acceptance_criteria: [AC-44]
risk_zone: red
status: in-progress
epic: A-02
plan_key: A-02-T23
branch: s12-ledger
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Hannah Leclerc's request sends one email naming Brightwater Hale to the entity's owners and adds
one POR-02 to-do that clears when Tess Moreno reconnects."

## Plan
- `POST /v1/connections/{id}/reconnect-requests` goes live (`integrations/client_connect.py`
  `reconnect_request`): the connection's entity, then `connection.reconnect_request` on an
  engagement of it (`authorised_engagement`: walls and other clients 404; firm partner, manager,
  senior; independence), then `connections.portal_v2` (404 off), replayed through
  `Idempotency-Key`.
- `connections/reconnect.py` `request_reconnect`: one unit of work; the engagement relocked and
  re-authorised; the connection locked, live and on the entity (else 404); one open request per
  connection (the 0195 partial unique index; a second ask answers the open one, `created=False`,
  nothing recorded or sent). Audited `connection.reconnect_requested` (identifiers only).
- Email: for a new request only, the Reconnect request template (`reconnect_request`, R-01's
  database rows) through `communications.send_templated` as the requesting person, to each active
  `client_admin` grant holder covering the engagement (`identity.client_owners`); values
  `client_first_name`, `firm_name` (Brightwater Hale), `connection_name` (the catalogue's name,
  never the masked label), `portal_link` (the portal). Idempotency per request and recipient; a
  missing template or a lint finding is recorded `blocked` by communications.
- Notification kinds `connection_needs_reauth` and `connection_reconnect_requested` registered
  (C16) for the drawer and preferences; the client's email is the template itself (notification
  email is staff-only, INV-4), so no catalogue event fans out (as `follow_up_sent`).
- POR-02 to-do: `portal/home_sources/connections.py` counts open reconnect requests on live
  connections of the scope's engagements' entities where the person holds `connection.read`
  (the client Owner); the to-do (`reconnect`, target POR-16) clears when the reconnect
  completes (`fulfil_reconnect_requests`, A-02-T16). Module edges `portal → connections`
  (DEC-517) and `integrations → communications`.
- Tests: `tests/integration/test_a02t23_reconnect_requests.py` (AC-11.1: one row, one email per
  owner naming Brightwater Hale, second ask sends nothing, to-do appears and clears on reconnect,
  walls/other client 404, agent and staff refused, flag off 404); app gates and route
  introspection updates.
- Rollback: flag `connections.portal_v2` off.

## Progress log
- 2026-10-27: plan written.
- 2026-10-27: built as planned (DEC-611). Any live connection may be asked about; the email goes
  after the request commits (not relayed). No outbox event yet (no consumer). LIST-001 exempts
  `identity.repository.owner_holders`.
