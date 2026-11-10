# TXP-11 · Workpaper · Ridgeline workbook, sheet 05 Capital

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/workpaper` (`?sheet=05&cell=H12&version=`) |
| Template and host frame | T6 spreadsheet grid grammar (`WorkbookGrid`) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-11 Workpaper - Ridgeline workbook- sheet 05 Capital/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Olivia Brandt (Tax Senior, preparer) |
| Flags | `tax.entity_workspace` |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | Cell selected from issue | `05 Capital!H12` selected from the M-2 issue; formula bar "(empty) — expected ='06 Schedule K'!C31 × 25% → 1,550"; H8:H12, J13, J15 cited | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only, **lock proposed** | planned |
| a2 | Citation · SHL-07 | D12 citation → 2024 K-1 Item L | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | planned |
| a3 | Field provenance · SHL-09 | Provenance on J12 | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | planned |
| b | Fix proposed | Proposed pills on H8:H12 = 124 · 2,356 · 2,015 · 155 · 1,550 | Mon Sep 14, 2026, 9:24 AM CT | proposal open | D (blocking) · C report-only | planned |
| b2 | Fix approved | Pills turn "✓ SI"; J13 = 6,866,200 = J15; the tab's amber dot clears | Mon Sep 14, 2026, 9:24 AM CT | after approval | D (blocking) · C report-only | planned |
| c | 01 Trial Balance | Sheet 01; `I18 = F18+G18+H18` → (94,000) | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | planned |
| d | Linked evidence · SHL-08 | Harborline municipal bond fund statement, Dec 2025, p. 1 | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | planned |
| e | Editing | H12 edited in the cell and the formula bar by Olivia (saves checkpoint "Edited 05 Capital!H12 by Olivia Brandt") | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-11 a, a2, a3, b, b2, c, d, e` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/workbook`
- `GET /v1/tax-returns/{id}/workbook/sheets/{sheet}?version=&range=`
- `GET /v1/tax-returns/{id}/workbook/cells/{address}?version=`
- `PUT /v1/tax-returns/{id}/workbook/cells/{address} (expected_version)`
- `GET /v1/tax-returns/{id}/workbook/export.xlsx`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Linked-issue chip | TXP-10 | planned |
| Cell citation | SHL-07 / SHL-08 | planned |
| Cell | SHL-09 | planned |
| Open in Excel | `Ridgeline_2025_1065_Workbook_v2.xlsx` | planned |

## Notes

Nine sheets per pack 08: 01 Trial Balance · 02 Fixed Assets · 03 Liabilities · 04 Partner Txns · 05 Capital · 06 Schedule K · 07 M-2 · 08 States · 09 K-1s (the catalogue's "05 States" loses). Edits are preparer-only (DEC-84). Version picker "Version 2 · Run 2". Agent-written versus human-edited cells stay distinguishable. Formulas use ADR-237's closed grammar.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-11 acceptance: <criterion>".
