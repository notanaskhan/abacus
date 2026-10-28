---
id: TASK-1612
title: First live ledger read connector, QuickBooks Online (A-02-T26)
spec: SPEC-333
acceptance_criteria: [AC-36, AC-49]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T26
branch: s13-a02-t26
created: 2026-10-27
updated: 2026-10-27
---

## Objective
A QuickBooks Online connector that authorises, rotates its refresh token, pulls the TrialBalance report and normalises it into the existing pipeline, read-only and egress-bound.

## Plan
- `connections/connectors/quickbooks_online.py`, `connections/qbo_format.py`, pipeline dispatch by `run.source`, factory and reseal in `connections/service.py`, `qbo_app()` in `connections.api`.
- `integrations/qbo_adapter.py`, registered only with the app registration; `ports.ReadPost`, `registry.read_posts()`, `egress_read_posts()`; API and worker configure egress with the read POSTs.
- `write-capabilities.yaml`: read connector entry; W1 writer renamed `quickbooks_online_poster`.
- Settings `qbo_client_id`, `qbo_client_secret`, `qbo_environment`. AUTH-002 excludes this connector (outbound header only).
- Tests `tests/unit/connections/test_qbo_connector.py` with a synthetic recorded report fixture.
- Rollback: unset the settings (nothing registers); revert.

## Progress log
- 2026-10-27: built; DEC-709. Also fixed A-02-T25's `ACTIVITIES` redefinition (pyright). Tests in the batch pass.
