---
id: TASK-8098
title: W-01-T07 Connect catalogue service — effective status, counts, search, blocked reasons, Notify me, v2 import with dry run, log and availability fan-out
spec: SPEC-659
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-31, AC-32, AC-33]
risk_zone: red
status: in-review
branch: w01-t07-catalogue-service
created: 2026-11-15
updated: 2026-11-15
---

## Objective
WB-10's live read and the catalogue's v2 import (DEC-5072).

## Plan (red)
- Migration 0901 (expand-only): `category` nullable for workbench-only rows (portal rows keep it), `prerequisite` content column, `integration_catalog_workbench()` for the app, `integration_catalog_import(...)` and `integration_catalog_import_log()` for `abacus_ops`. Rollback: downgrade drops the functions and the column and restores NOT NULL (refused while a workbench-only row exists: hide it first).
- Service `integrations/connect_catalog.py`; plan `integrations/catalog_import.py`; fan-out `integrations/availability.py`; event `integration.available`; C16 kind `integration_available`.
- Routes: `GET /v1/integrations/catalog` and `POST /v1/integrations/{key}/interest` wired; person-scoped actions authorise with `authorise_own` (identity gains `own_role_allows`).
- Ops command: `abacus_tools.integration_catalog import` (dry run, apply, plan check, fan-out).
- Tests: `tests/unit/integrations/test_w01t07_catalogue.py`, `tests/integration/test_w01t07_catalogue_import.py`.

## Partly built
- AC-7's `facts.reason = mfa_required` on a stale session: the router refuses before the handler; stays strict-xfail in the W-01 AC suite.
- A platform-wide per-integration kill switch (ADR-157 proposed): "Paused" reads from the install's status only.
- The import routes (`/v1/platform/integration-catalog/imports`) stay 501: no principal holds `integration_catalog.import`; the operator imports through the ops command (AC-32).

## Progress log
- 2026-11-15: built; unit and integration tests green; stacked on #2097.
- 2026-11-16: AC-7's `facts.reason = mfa_required` built in TASK-8112 (the Connect gate, not the router); the strict xfail is removed. The import routes stay 501 by design (AC-32: the operator's command).
