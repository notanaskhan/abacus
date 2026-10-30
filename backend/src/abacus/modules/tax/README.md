# tax

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Will own (docs/plan/03-backend-architecture.md §2.2): Tax returns, worksheets, fields, K-1s, basis and capital accounts, fixed assets, book-tax items, state apportionment, trusts and estates, filings, transmissions and acknowledgements, extensions, estimates, amendments. Red paths: `approval.py`, `export.py`, `filing.py`.

## Today (F-03-T22, migration 0089)
- **Table:** `tax_returns`, the `tax_return` work-item subtype: one row per work item, with its own `client_entity_id`, `form` (1040, 1041, 1065, 1120s, 1120, 990, 706, 709) and `tax_year`. Insert-only for the app; the columns it may insert are in `registry.py`.
- **Kind:** `api.py` registers `tax_return` with engagements' work-item kind slot (`TaxReturnKind` in `kind.py`). Create one with `engagements.api.create_work_item(ctx, engagement_id, "tax_return", name=..., client_entity_id=..., details={"form": "1040", "tax_year": 2026})`.
- **Routes:** the engine-bridge and e-file-record stubs (`engine_contract.py`, T-01-T02): 21 routes at 501 behind `tax.engine_bridge` and `tax.delivery_efile`.

## Seam with T-02 (T-01-T02)
T-01 owns four **red** files, declared protected by T-01-T07: `approval.py` (final approval; the
only writer of a tax return's `final_approval` sign-off, TAXAPPROVE-001), `export.py` (the engine
workbook after approval), `filing.py` (the 8879 amount binding, the ERO's transmission record and
acks; never a transmission, R-04) and `tri.py` (TRI helpers). T-02 owns `tax_returns`' columns and
the status machine (`status.py`) and calls final approval through `tax.api`; T-01 never adds a
column to `tax_returns`.
