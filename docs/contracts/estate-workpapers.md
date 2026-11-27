# Estate workpapers · EW-1 (v1)

> **T-06-T69 (DEC-6024):** the routes answer 404 without the firm's `tax_returns` entitlement, which replaced `tax.estate_workpapers`.

| Field | Value |
|---|---|
| Version | v1 |
| Status | **stub** (T-07-T05, 2026-11-14); every route answers 501 behind `tax.estate_workpapers` until T-07-T22 |
| Provider epic | T-07 (SPEC-656) |
| Consumers | TXT-04 (T-07-T26); T-08 (HOME-03 due-date facts); R-03 (POR-18 estate intake hand-off); Q-05 (FIL-02 record types) |
| Flags | `tax.estate_workpapers` |
| Code | `backend/src/abacus/modules/tax/estate_contract.py` |
| Matrix | `estate_workpaper.read`, `estate_workpaper.edit` in `docs/architecture/permission-matrix/tax.yaml` (T-07-T03) |

## 1. Who may call it
A client principal 404; the flag off 404; the route's one action (walls first, 404); then 501.
Every write is a person's; `valued` needs ≥ 1 citation and a human setter.

## 2. Routes

| Method · path | Action | Response |
|---|---|---|
| `GET /v1/tax/returns/{return_id}/estate/inventory` | `estate_workpaper.read` | `EstateInventoryOut` (header with due chip and tallies, assets, totals) |
| `GET /v1/tax/returns/{return_id}/estate/deductions` | `estate_workpaper.read` | `EstateDeductionsOut` |
| `GET /v1/tax/returns/{return_id}/estate/computation` | `estate_workpaper.read` | `EstateComputationOut` (label `accrued_tie_out_shadow` until a CCH 706 import; `avd_available`; Illinois card status only) |
| `GET /v1/tax/returns/{return_id}/estate/gifts` | `estate_workpaper.read` | `EstateGiftsOut` (annual exclusion and taxable gift computed) |
| `GET /v1/tax/returns/{return_id}/estate/derivations/{tile}` | `estate_workpaper.read` | `EstateDerivationOut` |
| `POST /v1/tax/returns/{return_id}/estate/assets`, `PATCH /v1/tax/estate-assets/{asset_id}` | `estate_workpaper.edit` | `EstateAssetOut` |
| `POST /v1/tax/returns/{return_id}/estate/deductions`, `PATCH /v1/tax/estate-deductions/{deduction_id}` | `estate_workpaper.edit` | `EstateDeductionOut` |
| `POST /v1/tax/client-entities/{client_entity_id}/gift-history`, `PATCH /v1/tax/gift-history-items/{gift_id}` | `estate_workpaper.edit` | `GiftHistoryRowOut` |

Reused: P-04's `POST /v1/sign-offs` (L4 on `estate_workpaper`, engagement partner only), C5
appraisal requests with `linked_ref` (SHL-14), K-02's `GET /v1/due-dates`.

## 3. Shapes and rules
- Figures are TRI; names and descriptions Confidential. `basis_to_1041` is null for IRD and
  non-probate life insurance by rule (`basis_rule`), never by entry.
- The Illinois Form 700 card (`EstateStateCardOut`) has no money field (AC-13.3).
- Footing fixture: `backend/tests/contracts/fiduciary/fixtures/thornbury_706.json` (gross estate
  16,400,000 − deductions 900,000 = taxable estate 15,500,000).
