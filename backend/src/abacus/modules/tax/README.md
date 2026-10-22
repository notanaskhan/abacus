# tax

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Will own (docs/plan/03-backend-architecture.md §2.2): Tax returns, worksheets, fields, K-1s, basis and capital accounts, fixed assets, book-tax items, state apportionment, trusts and estates, filings, transmissions and acknowledgements, extensions, estimates, amendments. Red paths: `approval.py`, `export.py`, `filing.py`.

## Today (F-03-T22, migration 0089)
- **Table:** `tax_returns`, the `tax_return` work-item subtype: one row per work item, with its own `client_entity_id`, `form` (1040, 1041, 1065, 1120s, 1120, 990, 706, 709) and `tax_year`. Insert-only for the app; the columns it may insert are in `registry.py`.
- **Kind:** `api.py` registers `tax_return` with engagements' work-item kind slot (`TaxReturnKind` in `kind.py`). Create one with `engagements.api.create_work_item(ctx, engagement_id, "tax_return", name=..., client_entity_id=..., details={"form": "1040", "tax_year": 2026})`.
- **Routes:** none (`ROUTERS = ()`).
