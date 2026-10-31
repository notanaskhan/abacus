---
name: connector
description: How to build or change a connector to a client system — contract, read-only enforcement, pipeline stages, rate limits, tests. Use for any connector work.
---

# Connector pattern

**Reference:** `docs/architecture/reference/connector.md` and the fake connector (`modules/connections/fake.py`). Provider-specific notes: `docs/integrations/<provider>.md`.

## Contract (ADR-037)
Implement `capabilities`, `authorise_url`, `exchange_code`, `refresh`, `pull(dataset, period, cursor)`, `changes_since`, `fetch_attachment`, `health`. Pass the conformance suite: `backend/tests/unit/connections/conformance.py`, parametrised with `conformance_params({...})`. CONN-001 rejects write-shaped methods and network imports.

## Pipeline (ADR-038)
extract → raw (write-once, fingerprinted) → normalise (common ledger model with source IDs and authorship, ADR-039) → validate (control totals) → snapshot → render (deterministic, ADR-042). Never skip validation.

## Rules
- Read operations only; the HTTP client exposes no write methods (ADR-040).
- Every provider string is untrusted (ADR-064).
- Rate limiter per provider and company; chunked, idempotent, resumable pulls; circuit breaker (ADR-043).
- Tokens decrypted only inside the activity using them (ADR-035).
- Persist rotated refresh tokens; treat expiry as a normal state.

## Local runs
The fake connector reads `fake_connector_dir`; `make seed` connects engagements and writes balanced trial-balance fixtures (`abacus_tools.synthetic.connector_fixtures`).

## Tests (ADR-044)
Golden normalisation tests, property tests (balances), recordings from synthetic data only, conformance suite, nightly sandbox contract test.

## Adding a second live ledger (A-02-T38; the QuickBooks Online read is the worked example)
1. **Connector** (`modules/connections/connectors/<provider>.py`, like `quickbooks_online.py`): the
   ADR-037 contract above, a format parser beside `qbo_format.py`, the provider code in
   `CONNECTORS`; grant failures map to the reauth reasons (`token_expired`, `invalid_grant`) so the
   daily health pass (`connections/health.py`) shows **Needs reauth** and refuses retries.
2. **Registry** (`docs/architecture/write-capabilities.yaml`, protected): a `read_connectors`
   entry with its `adapter_key`, `category: ledger`, every `egress_hosts` host (sign-in, OAuth,
   API), its `read_scopes` and the OAuth `read_posts`; `kernel.egress` refuses anything else.
   Regenerate `_capabilities.py` (`make generate`); the drift test holds both together.
3. **Adapter metadata** (`modules/integrations/<provider>_adapter.py`, like `qbo_adapter.py`):
   key, category, connection provider, read scopes and hosts matching the registry entry;
   registered only when the environment holds the app registration (catalogue honesty: a row
   reads Available only where a client can really connect).
4. **Catalogue row** (content, never code): add it to the reviewed catalogue document and load it
   with `abacus_tools.integration_catalog` (the ops role); consent copy is read-only (DF-19: no
   "post" copy or scope before P-16).
5. **Switches:** the firm's `connections.live_ledger` gates start, complete and pulls (a running
   pull ends `connector_paused`); `connections.portal_v2` gates POR-16 and reconnect requests.
6. **Tests:** the conformance suite; `write_interception.intercept()` around every read with
   `assert_read_only()`; recorded responses from the provider's sandbox with synthetic companies
   only; the kill-switch test pattern (`test_a02t33_kill_switch.py`).
7. **Runbooks:** RB-04 (provider outage) and RB-05 (expiring-connections wave) name the provider's
   status page and its token lifetime.
