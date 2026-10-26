---
id: TASK-1339
title: Integrations framework v1, migration 0194, adapter registry, catalogue read and load (A-02-T12)
spec: SPEC-333
acceptance_criteria: [AC-49, AC-50]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T12
branch: s10b-ledger-integrations
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"An unregistered adapter is never listed as available, secrets are sealed with the tenant key and
the owner id as associated data, and a dry-run load reports adds and changes without writing."

## Plan
- Migration `0194_integrations_framework.py`:
  - `integration_catalog` (global, A-02 §4.2 columns plus `loaded_by`): no app privilege
    (schema_check's global rule wins over the plan's "SELECT for the app role", same effect);
    `integration_catalog_rows()` definer for the app and `abacus_ops`;
    `integration_catalog_load(rows jsonb, operator text)` definer for `abacus_ops` only (adds,
    changes with a revision bump, never deletes). Scopes are `read` only (CHECK).
  - `firm_integrations` (tenant; one live install per app); `integration_secrets` (tenant,
    restricted; no UPDATE; DELETE removes the only sealed copy).
- Module `integrations`: `adapters.py` (fail-closed registry: grammar, category, hosts and scopes
  via `ReadConnectorEntry`, no write-shaped public method, one adapter per key and provider),
  `catalog.py` (read through the definer in `tenant_session`; `listing_of` gives `available`
  only for a registered adapter matching the row's category and provider), `catalog_load.py`
  (`CatalogDocument`, pure `plan_load`), `secrets.py` (seal with `binding(owner id)`, open,
  erase; audited `integration_secret.stored|erased` on target `firm_integration`), `models.py`,
  `registry.py`, `api.py`.
- CLI `abacus_tools/integration_catalog.py load --document --operator [--dry-run]`, local and
  dev only (security review M3: not an allowlisted ops command yet).
- schema_check: `NON_TENANT_TABLES`, `GLOBAL_TABLES`, `DEFINER_FUNCTIONS`, `OPS_ONLY_FUNCTIONS`;
  `test_schema_check_db.py` expected definers; audit target `firm_integration` firm-level.
- Tests: `tests/unit/integrations/test_framework.py`, `tests/integration/test_integrations_schema.py`.
- No route, flag or matrix change (POR-16 routes are A-02-T16; the write registry A-02-T15).
- Rollback: downgrade drops the three tables and two functions; nothing reads them yet.

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
- 2026-10-26: security review fix round (DEC-438, DEC-439 notes): M1 adapter allowlist, M2 consent
  links bound to one client entity (0195 amended in place), M3 the catalogue load is local and
  dev only (removed from the ops allowlist), L5 load checks the plan, L4 erase wording. Targeted
  tests: 79 passed (unit framework, release and deploy workflows, the two schema files, the
  update-column contract test); gates clean.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-438 | Catalogue as a global table behind definers; honesty rule; secret binding; no catalogue content committed | No |
