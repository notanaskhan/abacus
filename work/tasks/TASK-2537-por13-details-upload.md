---
id: TASK-2537
title: "POR-13 W-9/W-8 upload in a K-1 recipient's scope (T-02-T27 open piece)"
spec: SPEC-502  # AC-5; docs/screens/POR-13.md d; T-02 §3.7, DV-10
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: T-02
plan_key: T-02-T27
branch: s20e-por13-upload
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Close T-02-T27's open piece: POR-13 d's "Update taxpayer ID" sends a signed W-9 or W-8 as the
recipient's own upload, for a person at the firm to accept (DV-10).

## Plan (amber)
- Contract first: `POST /v1/portal/k1-recipients/{rid}/details-changes:upload`; `make generate`.
- `tax/k1_portal.py`: `upload_details_change` (scan, detached-key store, `evidence.api.add_version`,
  the pending change); the address route takes addresses only (DEC-1578).
- POR-13: the sheet live (W-9 or W-8, file chooser, Send); fixture handler; tests.
- Tests: `tests/integration/test_t02t27_details_upload.py`; POR-13 vitest.

## Progress log
- `2026-11-01` — Built on `s20e-por13-upload`. Integration 3 + T-02-T26 3 passed; POR-13 11 passed.
