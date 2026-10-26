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

- 2026-10-26: one targeted pass at the end of the wave (brief step 7): 1,520 backend tests in the
  touched and covering files (unit integrations, assurance, ledger, workpapers ties, audit
  targets, release and deploy workflows; C9 and C20 contract suites; the three new schema files,
  test_tb_versions, test_schema_check_db, test_retrieval; security a02t10, c09 authz, route
  introspection, tenant isolation, audit targets): 5 failed, fixed, re-run green (expected-map
  and consumer 501 updates; the a02t10 test now turns on `g2_blocks_view` on an attest
  engagement, since G2 binds reads only there, ADR-164; fieldwork registers the adjustment
  source, so all four layers exist in the app). Vitest AUD-06, AUD-02, C9 and C20 fixture
  contracts: 73 passed. Gates: ruff format/check, pyright, lint-imports, banned_patterns,
  error_codes, validate_docs, scope_guards, fresh_mfa, secrets_scan, check-heads,
  check-generated; tsc, eslint, prettier on touched files. Playwright not run.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-439 | Consent link table, connection_states provider widened too, reason-code list, retention record type left to content | No |
