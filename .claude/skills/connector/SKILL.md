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
