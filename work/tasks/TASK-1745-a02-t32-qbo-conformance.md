---
id: TASK-1745
title: A-02-T32 QuickBooks Online connector conformance (ADR-044), fake per PR and sandbox nightly
spec: SPEC-333
acceptance_criteria: [AC-38]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T32
branch: s14-a02-t32
created: 2026-10-29
updated: 2026-10-29
---

## Objective
One conformance suite for the live ledger connector and its pull pipeline in
`backend/tests/connectors/quickbooks_online/`, against the fake on every pull request and the
sandbox nightly: golden normalisation, Hypothesis property tests, the real-identifier block.
Acceptance (backlog row): "The suite passes on the fake and on the sandbox, and a drifted fake
marks dependent journeys unverified in the weekly quality report." (Chapter 10 §10.7.4.)

## Plan (red: tests, a quality tool, CI wiring; no product code)
- Suite: `targets.py` (fake = the real connector over A-02-T27's `RecordedQbo`; sandbox = the real
  connector over the kernel egress client when `ABACUS_QBO_SANDBOX_*` are set), `conftest.py`
  (the `target` fixture; no sandbox case without credentials), `test_conformance.py` (port
  surface, PKCE and scope, rotation and reseal, period and dispatch, `ledger.validate`, health,
  read-only requests, fake-only failure codes), `test_golden_and_properties.py` (golden YAML,
  Hypothesis), `test_drift_report.py` (unverified journeys, the real-identifier block), one
  synthetic recording and its golden.
- `abacus_tools/quality/connector_conformance.py`: `DEPENDENT_JOURNEYS` (§10.6.6: J02, J05, J10),
  `record`, `unverified`, `failing_fakes`, the recording scan and its CLI.
- `abacus_tools/quality/report.py`: the Contracts area gains "Unverified fakes" from
  `connectors.json`; "Fixture-versus-live drift" keeps its own row.
- `Makefile` `UNIT_TESTS` gains `tests/connectors` (per-PR CI); `.github/workflows/
  connectors-nightly.yml` (fake and sandbox, outcome artifact); `quality-report.yml` downloads the
  last finished night.
- DEC-835. Rollback: revert the branch (the nightly job only reads).

## Progress log
- `2026-10-29` — Built and run: 49 passed on the fake (no sandbox credentials here); workflow
  shape, paths and quality report suites green (87); ruff, pyright, lint-imports, banned patterns
  and the secrets scan clean. The sandbox target is unproven until the secrets exist.

## Handoff
- **Current state:** PR open, held for the batch.
- **Human to-do:** add repository secrets `QBO_SANDBOX_CLIENT_ID`, `QBO_SANDBOX_CLIENT_SECRET`,
  `QBO_SANDBOX_REFRESH_TOKEN`, `QBO_SANDBOX_REALM_ID` (Intuit developer sandbox company), then
  dispatch `connectors-nightly` once.
- **Next:** N-01-T11.
