---
id: TASK-1340
title: Entity-scoped connections, migration 0195 (A-02-T13)
spec: SPEC-333
acceptance_criteria: [AC-35, AC-37, AC-42, AC-46]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T13
branch: s10b-ledger-integrations
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Existing connections and sync runs survive up/down/up unchanged, a second live QuickBooks
connection for one entity is refused, and a bank feed beside the ledger is allowed."

## Plan
- Migration `0195_entity_connections.py` (A-02 §4.2 T13 rows): provider CHECK to the key grammar
  (connections and connection_states); new connection columns (category backfilled `ledger`,
  external_account_ref, masked display_label, connected_by_user_id/connected_at, reauth_due_at,
  last_sync_at, status_reason_code); drop `connections_one_live`, add
  `connections_one_live_account` and `connections_one_live_ledger`; `sync_runs.request_item_id`
  nullable, `trigger` (backfill `request_item`), `label`, dataset widened, trigger/item CHECK;
  `connection_consents` and `connection_consent_links` (insert-only with triggers);
  `reconnect_requests` (one open per connection; UPDATE `fulfilled_at` only).
- Registry and models (`connections/registry.py`, `models.py`); the two code paths that assume a
  request item fail closed for a run without one (`service._view` 404, the pipeline's render
  stage terminal) until A-02-T30 patches the workflow.
- schema_check `IMMUTABLE_TABLES` and the expected map.
- The C20 stub's disconnect stays on `connection.disconnect` (DEC-379; A-02-T16 implements it);
  `connection_secrets` and its delete-on-revoke crypto-erase are untouched.
- Tests: `tests/integration/test_entity_connections_schema.py`.
- Rollback: downgrade restores the old shape; it refuses (constraint errors) once a second live
  connection per entity or a run without a request item exists, which is local only (P-38).

## Progress log
- 2026-10-26: plan written; built with the rest of S10 wave B.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-439 | Consent link table, connection_states provider widened too, reason-code list, retention record type left to content | No |
