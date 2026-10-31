---
id: TASK-2524
title: T-01-T41 Filed-return delivery
spec: SPEC-501  # T-01 §3.14; docs/contracts/efile-record.md
acceptance_criteria: [T-01-§3.14]
risk_zone: amber
status: in-review
epic: T-01
plan_key: T-01-T41
branch: s20c-t01-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-10-31
updated: 2026-10-31
---

## Objective
`deliverable.publish` by client service after acceptance and packet approval; portal home source
`tax_filings.py` adding Earlier rows with scope_only and TRI MFA; audited client-copy download;
a migration path to C10 for R-02.

Acceptance (backlog row): "Claire Feld sees 2025 Form 1040 filed and accepted with a download on
her home after two-step, and Meera Shah sees nothing of the Feld household."

## Plan (amber)
- Migration 0526 `filed_return_deliveries` (insert-only, human-actor CHECK); `return.delivered`
  in the human-only list.
- `tax/filed_delivery.py`: `publish`, `filed_returns`, `client_copy`; tax.api exports.
- `portal/home_sources/tax_filings.py` registered in `home.py`.
- Routes: publish live; `GET /v1/portal/filed-returns/{delivery_id}/download`.
- Registries and tenant list; `make generate`.
- Tests: `test_t01t41_filed_return_delivery.py`.
- Rollback: downgrade 0526; revert the routes.

## Notes
- Stacked on T-01-T37 (`s20c-t01-t37`).
- The `deliverable_ready` email and the consents Earlier row stay open (DEC-1571).

## Progress log
- `2026-10-31` — Built on `s20c-t01-t41`. T41 tests 3 passed.
