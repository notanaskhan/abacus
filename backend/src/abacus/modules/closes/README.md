# closes

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Will own (docs/plan/03-backend-architecture.md §2.2): Monthly closes, close plans, procedures, reconciliations, schedules, arrangements, analytic lines, deliverables, 1099 vendors and W-9 requests. Posting lives in adjustments.

## Today (F-03-T22, migration 0089)
- **Table:** `closes`, the `close` work-item subtype: one row per work item, with its `period` (`YYYY-MM`). One close per engagement and period (`UNIQUE (tenant_id, engagement_id, period)`). Insert-only for the app; the columns it may insert are in `registry.py`.
- **Kind:** `api.py` registers `close` with engagements' work-item kind slot (`CloseKind` in `kind.py`). `engagements.api.create_work_item(ctx, engagement_id, "close", name=..., details={"period": "2026-01"})` writes the work item and this row in one unit of work. A second close for the same period answers 409 `work_item_exists`.
- **Routes (then):** none (`ROUTERS = ()`); see the C-01 v1 section below for today's.

## C-01 v1 (C-01-T55, SPEC-655)
- **Routes:** the close work router (portfolio, record, runs, plans, intake, accounts, reconciliation, review, flux; `contract.py`, `contract_work.py`), the portal close router (POR-11 questions: client fields only) and the delivery router (C-02's). Every route is behind `closes.engine` (POR-11 also `closes.portal_requests`); model steps behind `closes.agent`.
- **Consumer API:** `api.py` only: `close_for` (CloseFacts), `close_summary`, `register_status_guard`, `open_exceptions`, `raise_exception`, `add_note`, the plan functions (`get_plan`, `create_draft`, `add_row`, `patch_row`, `publish`, `import_template`) and the request publish workflow (`RequestPublishWorkflow`, `schedule_publish`).
- **Compute:** `compute/` holds the pure functions (reconciliation, schedules, package) with `engine_version` and `inputs_hash`; money is `Decimal`; goldens in `backend/tests/golden/closes/` (ADR-050).
- **Reads only:** QuickBooks Online through `connections` (ADR-040); no AJE is posted (DV-1, DV-2).
- **Content:** close, email and question templates are database rows loaded through import endpoints (`import_template`, `add_request_template`), never constants.
- **Runbooks:** RB-93 `docs/runbooks/close-shadow-and-support.md`; RB-04 (connector outage) and its hourly-sync addendum.
- **Hand-offs:** `docs/plan/status/C-01-handoff.md` (C-02, K-04, W-02, W-03, I-01).
