# C20 · Integration framework and write-capability registry (v1)

| Field | Value |
|---|---|
| Register row | C20 in `docs/contracts/README.md` |
| Version | v1 |
| Status | stub (A-02-T06, 2026-10-26); framework v1 tables and module (A-02-T12) and entity-scoped connection tables (A-02-T13) built 2026-10-26, routes still stubs until A-02-T16 |
| Provider epic | A-02 (T06 stub; T12 framework, T13 entity-scoped connections, T15 registry, T16 POR-16 service, T23 reconnect requests, T30 pulls); W-01 adds the catalogue v2 (C20 v2, S45) |
| Consumers | POR-16 (A-02-T18 fixtures, T28 live); AUD-06 *Ask client to reconnect* and *Pull latest* (A-02-T24, T30); T-01 (CCH file bridge, `firm_integrations`, secrets); W-01 (catalogue v2); N-02 (W7 DocuSign registry entry); C-02 (W1 posting under ADR-161); C-01 (hourly sync); X-02 (POR-16 h, i); Q-01 (egress host allowlist) |
| Freeze sprint | S10 (2027-03-08) |
| Flag | `connections.portal_v2` (POR-16 routes and reconnect requests) and `connections.live_ledger` (on-demand pulls), both default off, expire 2027-04-21 |
| Spec | `docs/specs/SPEC-333-trial-balance-and-ledger-connections.md` (AC-35 to AC-51) |
| ADRs | ADR-136 (P-17, DEC-46), ADR-040, ADR-108, ADR-031, ADR-139; DF-19 |

## 1. Purpose
Consumers can rely on POR-16's shapes (the entity's connection cards, the consent sheet, the details drawer, start, retry and disconnect), the firm's reconnect request and on-demand pull, and two framework ports: the `IntegrationAdapter` protocol (read-only by construction) and the schema of the protected `docs/architecture/write-capabilities.yaml` (read connectors with egress hosts; writes reserved, never enabled in v1). A **connection** is the client-authorised, read-only link to a client entity's system; an **integration** is a firm-installed or personal app (A-02 naming note).

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| POR-16 cards | `GET /v1/portal/entities/{entity_id}/connections` | `connection.read` | client_admin (`scope_only`, the entities the grant covers); engagement partner, manager, senior on an engagement for the entity (independence) | denied |
| Start with consent (`Idempotency-Key`, 201) | `POST /v1/portal/entities/{entity_id}/connections/{catalog_key}/start` | `connection.create` | client_admin; fresh MFA | denied |
| Details drawer | `GET /v1/portal/connections/{connection_id}` | `connection.read` | as cards | denied |
| *Try again* (`Idempotency-Key`, 202) | `POST /v1/portal/connections/{connection_id}/retry` | `connection.retry` | client_admin (`scope_only`); engagement partner, manager | denied |
| Disconnect (`Idempotency-Key`) | `POST /v1/portal/connections/{connection_id}/disconnect` | `connection.disconnect` | client_admin (`scope_only`: an entity the grant covers); fresh MFA, since the secret is destroyed | denied |
| Ask client to reconnect (`Idempotency-Key`, 201) | `POST /v1/connections/{connection_id}/reconnect-requests` | `connection.reconnect_request` | engagement partner, manager, senior; independence | denied |
| On-demand pull (`Idempotency-Key`, 202) | `POST /v1/engagements/{engagement_id}/connection/pulls` | `ledger.pull` | engagement partner, manager, senior; independence | denied |

Matrix rows: `docs/architecture/permission-matrix/connections.yaml` (A-02-T02, TASK-1185; `connection.disconnect` added by the A-02-T06 security review, DEC-379: the legacy engagement route keeps the looser `connection.revoke`, the portal route never uses it). Stubs check the flag before anything else, as every stub on main does; the implementing tasks authorise first (a wall answers 404 before the flag or any read). Flag off: 404. Flag on: 501 `not_implemented` until the task named in each route's docstring. Firm staff cannot start a client connection (only `client_admin` holds `connection.create`); a third party holds no cell (AC-41).

Module interface (`integrations.api`): `IntegrationAdapter` (`key`, `category`, `connector_provider`, `read_scopes()`, `egress_hosts()`; no write method), `WriteCapabilityRegistry` (`version: 1`, `read_connectors[]`, `writes[]`, `egress_hosts()`), `ReadConnectorEntry`, `WriteCapabilityEntry` (`enabled` is `false` by type), `IntegrationCategory`. Other modules import only `integrations.api` (DEC-13).

## 3. Models
Code: `backend/src/abacus/modules/integrations/contract.py` and `ports.py`.

- `PortalConnectionsOut` `{entity: {client_entity_id (internal), display_name (confidential)}, firm_display_name (public), items: PortalConnectionCardOut[] ≤ 50}`.
- `PortalConnectionCardOut` `{catalog_key, name (public), category, icon (a Lucide glyph name, public), tone (olive | espresso | clay | ochre), status: IntegrationStatus, status_reason? (token_expired | invalid_grant | sync_failed | provider_unavailable), connection_id?, display_label? (masked, confidential), connected_by? {user_id, display_name (confidential), kind: client | firm}, connected_at?, reconnected, last_sync_at?, last_failed_at?, reauth_requested_at?, helper? (catalogue copy, public), scopes: {code, label}[] (read scopes only), consent?: ConsentCopyOut, export_instead?: {request_item_id?, binder_id?}, version, allowed_actions: (connect | reconnect | details | disconnect | retry | export_instead)[]}`.
- `ConsentCopyOut` `{version, title, will[], wont[], authorization, continue_label, helper?}`: catalogue content (A-02-T12 loads it; never seeded constants), public.
- `ConnectionStartIn` `{consent_version ≥ 1, authorized: bool}` · `ConnectionStartOut` `{consent_id, authorise_url (restricted: carries the single-use state, never logged), expires_at}`.
- `PortalConnectionDetailOut` `{card, recent_syncs: SyncRunSummaryOut[] ≤ 5}` · `SyncRunSummaryOut` `{sync_run_id, trigger (request_item | on_demand | schedule | export), status (the `sync_runs` codes), started_at, finished_at?, failure_code?}`.
- `ConnectionDisconnectIn` `{seen_version}` · `SyncRunRefOut` `{sync_run_id, status}` · `ReconnectRequestOut` `{id, connection_id, requested_by, requested_at}` · `LedgerPullIn` `{period_end (confidential), label: TrialBalanceLabelStatus = standard}`.
- `WriteCapabilityRegistry` and its entries: hosts are lower-case DNS names (no scheme, wildcard or single label); keys `^[a-z][a-z0-9_]{1,49}$`; a write's `shape` is `W1`…`W9` with its owner epic.

## 4. Status words
C2 `integration` (`docs/product/status-vocabulary.yaml`): `connected` "Connected", `needs_reauth` "Needs reauth", `needs_attention` "Needs attention", `connecting` "Connecting", `disconnected` "Disconnected" (neutral), `available` "Available" with the portal's `client_label` "Not connected" (added here for POR-16 a), `coming_soon`, `paused`. The repo's `connections.status` codes bridge to these (`active` → `connected`; `needs_attention` splits on the failure code; `revoked` → `disconnected`).

## 5. Human-only actions
Every action above denies the agent and the system principal (INV-1, SPEC-333 AC-30). `connection.create` is the client's alone, with a fresh second factor. A future `write_capability.execute` (A-02-T15) is declared with no allowed role.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not_found"}` | flag off; another client's entity or connection (INV-4) |
| 422 | `{"detail": "authorization_required"}` | start without the authorization toggle (AC-36) |
| 409 | `{"detail": "consent_version_stale"}` | the sheet's copy is older than the catalogue's |
| 409 | `{"detail": "ledger_already_connected"}` | a second live ledger for the entity |
| 409 | `{"detail": "connector_not_available"}` | the catalogue row's adapter is not registered here (AC-49) |
| 409 | `{"detail": "connection_needs_reauth"}` | retry or pull on a connection that needs the client |
| 409 | `{"detail": "stale_version"}` | disconnect with an old `seen_version` |
| 501 | `{"detail": "not_implemented"}` | flag on, until the implementing task |

A reconnect request while one is open returns the open request and sends nothing (one open request per connection).

## 7. Audit and outbox events
| Event | Written when | Payload (no Restricted data) |
|---|---|---|
| `connection.started`, `connection.consent_recorded` | start | entity id, catalogue key, consent version |
| `connection.created`, `connection.reauthorized` | complete | connection id, actor "(client)" |
| `connection.retry_requested` | Try again | connection id, sync run id |
| `connection.revoked` | disconnect ("Disconnected by …") | connection id |
| `connection.reconnect_requested` | firm asks | connection id, engagement id |
| `ledger.pull_requested` | pull | engagement id, sync run id, label |

Outbox: `connection.created`, `connection.revoked` (exist), `connection.reauthorized`, `connection.status_changed`, `connection.reconnect_requested`.

## 8. Example payloads
Tess Moreno (Owner) on Copperleaf Coffee Roasters, Inc., Mon Sep 14, 2026, 9:24 AM CT (POR-16 a; Brightwater Hale, synthetic): QuickBooks Online "Connected" by Tess on Mar 4, 2026, last sync 9:15 AM, scope "Read ledger" (DF-19: no posting scope); Front Range Bank ••4410 "Connected", bank feed daily, last sync 6:02 AM; American Express ••1009 "Needs reauth" (`token_expired`, asked Sep 10) with the consent copy "Reconnect American Express"; Square "Connected"; Shopify and Payroll provider "Not connected". The full fixtures, a to g: `apps/web/src/fixtures/seed/connections.ts`.

A start without the toggle:
```json
POST /v1/portal/entities/{copperleaf}/connections/american_express/start
{"consent_version": 1, "authorized": false}
→ 422 {"detail": "authorization_required"}
```

## 9. Consumer contract tests
`backend/tests/contracts/c20_integrations/test_c20_stub.py` (provider: one action per route, 404 and 501, Idempotency-Key, classification, the empty registry, no write); `backend/tests/contracts/c20_integrations/test_c20_consumers.py` (A-02-T08: POR-16's shapes on the Copperleaf facts, refusal codes, registry words, agent refusal); `apps/web/src/fixtures/contracts/c20-integrations.contract.test.ts` (the a-g fixtures match the OpenAPI document, no posting copy, the start refusals). Fixture mode: `apps/web/src/fixtures/scenarios/POR-16.ts`.

## 10. Versioning
Additive changes in place. Breaking changes ship as v2 with one sprint of overlap.

| Version | Frozen on | Overlap ends | Notes |
|---|---|---|---|
| v1 | (S10, planned) | | stub A-02-T06 |

## 11. Open points
Decided in DEC-377 (flags, status codes per route, the reconnect request's idempotence, `client_label` "Not connected", DF-19 masking in the fixtures). POR-16 h and i (Tessellate, HR and ticketing) are X-02's.

## A-02-T12 and A-02-T13 (2026-10-26)

- **Framework v1** (migration 0194; `integrations.api`): `integration_catalog` is global content
  the app reads through `integration_catalog_rows()` and an operator loads from a reviewed document
  with `python -m abacus_tools.integration_catalog load --document … --operator … [--dry-run]`
  (`integration_catalog_load(rows, operator)`, `abacus_ops` only; adds and changes with a revision
  bump, never deletes; a dry run prints the same plan and writes nothing). Scopes are `read` only
  by CHECK and by the document's schema. `register_adapter` is fail-closed (grammar, category,
  hosts and scopes, no write-shaped method, one adapter per key and per provider);
  `listing_of(row)` is `available` only for a registered adapter matching the row's category and
  provider (AC-49). `firm_integrations` (one live install per app) and `integration_secrets`
  (sealed with the tenant key, the install's id as associated data; delete is the crypto-erase).
  No catalogue content is committed: the document is reviewed content, loaded per environment.
- **Entity-scoped connections** (migration 0195): provider by key grammar; `category`,
  `external_account_ref`, masked `display_label`, `connected_by_user_id`/`connected_at`,
  `reauth_due_at`, `last_sync_at`, `status_reason_code` (§3's reasons); one live connection per
  entity, provider and account, one live ledger per entity; `sync_runs.trigger` and `label`,
  nullable `request_item_id` only for runs no request item asked for; insert-only
  `connection_consents` with `connection_consent_links`; `reconnect_requests` with one open per
  connection. The portal disconnect keeps `connection.disconnect` (DEC-379) and the secret's
  crypto-erase when A-02-T16 implements it.
