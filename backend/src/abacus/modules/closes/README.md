# closes

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Will own (docs/plan/03-backend-architecture.md §2.2): Monthly closes, close plans, procedures, reconciliations, schedules, arrangements, analytic lines, deliverables, 1099 vendors and W-9 requests. Posting lives in adjustments.

## Today (F-03-T22, migration 0089)
- **Table:** `closes`, the `close` work-item subtype: one row per work item, with its `period` (`YYYY-MM`). One close per engagement and period (`UNIQUE (tenant_id, engagement_id, period)`). Insert-only for the app; the columns it may insert are in `registry.py`.
- **Kind:** `api.py` registers `close` with engagements' work-item kind slot (`CloseKind` in `kind.py`). `engagements.api.create_work_item(ctx, engagement_id, "close", name=..., details={"period": "2026-01"})` writes the work item and this row in one unit of work. A second close for the same period answers 409 `work_item_exists`.
- **Routes:** none (`ROUTERS = ()`).
