# tax

Zone: amber. Pre-registered by F-03-T08 (ADR-140).

Will own (docs/plan/03-backend-architecture.md §2.2): Tax returns, worksheets, fields, K-1s, basis and capital accounts, fixed assets, book-tax items, state apportionment, trusts and estates, filings, transmissions and acknowledgements, extensions, estimates, amendments. Red paths: `approval.py`, `export.py`, `filing.py`.

## Today (F-03-T22, migration 0089)
- **Table:** `tax_returns`, the `tax_return` work-item subtype: one row per work item, with its own `client_entity_id`, `form` (1040, 1041, 1065, 1120s, 1120, 990, 706, 709) and `tax_year`. Insert-only for the app; the columns it may insert are in `registry.py`.
- **Kind:** `api.py` registers `tax_return` with engagements' work-item kind slot (`TaxReturnKind` in `kind.py`). Create one with `engagements.api.create_work_item(ctx, engagement_id, "tax_return", name=..., client_entity_id=..., details={"form": "1040", "tax_year": 2026})`.
- **Routes:** the engine-bridge and e-file-record stubs (`engine_contract.py`, T-01-T02): 21 routes at 501 behind `tax.engine_bridge` and `tax.delivery_efile`.

## Compute (pure; ADR-050)
- `compute/transcripts.py` (T-01-T45, amber): parses IRS Wage & Income and Account transcript text
  and compares a Wage & Income transcript with the return as filed (`compare`), in exact
  decimals. No clock, database or I/O; hostile text is bounded and reported, never guessed at
  (DEC-1650). T-01-T43 stores the results.

## Tax profile (T-01-T43, red; DEC-1651)
- **Tables (0550):** `tax_profile_files` (staged uploads, consumed once), `tax_authorizations`
  (8821, 2848, state; CAF numbers sealed, last four kept), `tax_elections` (upsert with
  `seen_version`), insert-only `transcripts`, `transcript_lines`, `transcript_comparisons`.
- **Service:** `tax_profile.py` registers tax's half of CLI-05 with organisations
  (`register_tax_profile_backend`); organisations keeps the routes and their order of checks.
  The return as filed is `review.api.approved_values(..., 'engine_import')`, information returns
  as `ir.<form>.<n>.payer|amount`.

## Seam with T-02 (T-01-T02)
T-01 owns four **red** files, declared protected by T-01-T07: `approval.py` (final approval; the
only writer of a tax return's `final_approval` sign-off, TAXAPPROVE-001), `export.py` (the engine
workbook after approval), `filing.py` (the 8879 amount binding, the ERO's transmission record and
acks; never a transmission, R-04) and `tri.py` (TRI helpers). T-02 owns `tax_returns`' columns and
the status machine (`status.py`) and calls final approval through `tax.api`; T-01 never adds a
column to `tax_returns`.

## Returns workflow and K-1s (T-02, closed 2026-11-01)

T-02 owns `tax_returns`' columns and the status machine (`status.py`), the practice board and the
return frame's reads (`tax-returns.md`, frozen v1), and K-1 packages (`k1_packages.py` set import,
share and reads; `k1_release.py` and `k1_release_workflow.py` the red release with a ten-second
Undo; `k1_portal.py` the recipient's own packages, behind the second step for amounts; `k1-packages.md`,
frozen v1). A draft never reaches a portal (DEC-78); a full TIN refuses the file (DEC-52); a
details change stores no full TIN. Runbooks: RB-44 (shadow and the flips), RB-45 (K-1 bounce and
mis-release). Open: a route to revoke one package's `k1_recipient` grant.

