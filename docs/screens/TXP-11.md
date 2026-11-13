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
| Manifest status | fixture (T-05-T38) |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | Cell selected from issue | `05 Capital!H12` selected from the M-2 issue; formula bar "(empty) — expected ='06 Schedule K'!C31 × 25% → 1,550"; H8:H12, J13, J15 cited | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only, **lock proposed** | fixture |
| a2 | Citation · SHL-07 | D12 citation → 2024 K-1 Item L | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | fixture |
| a3 | Field provenance · SHL-09 | Provenance on J12 | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | fixture |
| b | Fix proposed | Proposed pills on H8:H12 = 124 · 2,356 · 2,015 · 155 · 1,550 | Mon Sep 14, 2026, 9:24 AM CT | proposal open | D (blocking) · C report-only | fixture |
| b2 | Fix approved | Pills turn "✓ SI"; J13 = 6,866,200 = J15; the tab's amber dot clears | Mon Sep 14, 2026, 9:24 AM CT | after approval | D (blocking) · C report-only | fixture |
| c | 01 Trial Balance | Sheet 01; `I18 = F18+G18+H18` → (94,000) | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | fixture |
| d | Linked evidence · SHL-08 | Harborline municipal bond fund statement, Dec 2025, p. 1 | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | fixture |
| e | Editing | H12 edited in the cell and the formula bar by Olivia (saves checkpoint "Edited 05 Capital!H12 by Olivia Brandt") | Mon Sep 14, 2026, 9:24 AM CT | Version 2 · Run 2 | D (blocking) · C report-only | fixture |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | fixture |
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
| Cell citation | SHL-07 / SHL-08 | built (DEC-4630) |
| Cell | SHL-09 | built (DEC-4630) |
| Open in Excel | `Ridgeline_2025_1065_Workbook_v2.xlsx` | planned |

## Notes

Nine sheets per pack 08: 01 Trial Balance · 02 Fixed Assets · 03 Liabilities · 04 Partner Txns · 05 Capital · 06 Schedule K · 07 M-2 · 08 States · 09 K-1s (the catalogue's "05 States" loses). Edits are preparer-only (DEC-84). Version picker "Version 2 · Run 2". Agent-written versus human-edited cells stay distinguishable. Formulas use ADR-237's closed grammar.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

### Designed states the handoff lacks (T-05-T03)

| State | What renders | None blank |
|---|---|---|
| Agent off | Cells written by the agent's steps never appear; every cell is code (a run's deterministic step), import or a person's edit; ▶ Run runs deterministic steps only. | yes |
| Flag off (`tax.entity_workspace`) | The 1065 opens TAX-02's coordination view as today (F13); no entity route answers and no pane renders blank. Not a screen state: the screen is unreachable. | yes |
| Consent blocked (§7216) | The run bar shows the waiting step with "§7216 AI consent — Ridgeline (1 of 2 signed)"; cells already computed stay; no model call. | yes |
| Import mode | Sheets fed by import-mode steps show "Imported · <file> · <date>" on their tab and their cells are read-only until T-06. | yes |
| Entitlement refused (`tax.entity_returns`, CPA memos unsigned, non-synthetic firm) | The return opens the coordination view with the designed locked card: title "Entity return workspace", body "Opens once the firm's entity returns are set up." (undesigned, T-05-T03), no workbook route answers (F13). | yes |

Every string above with no handoff source is undesigned (T-05-T03) and is replaced by the handoff's copy when one lands; the consent line is the spec's (SPEC-651 F13).

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-11 acceptance: <criterion>".

### Build notes (T-05-T38, DEC-4623)

- Built on the kit's WorkbookGrid: a (H12 selected, H8:H12 · J13 · J15 lit, the linked-issue chip, the 05 tab's amber dot), b (H8:H12 "Proposed"), b2 (after the fix, no open issue), c (01 Trial Balance, I18 `=F18+G18+H18` → (94,000)) and e (in-cell edit through `PUT …/workbook/cells/{sheet!A1}` with the cell's version; a 409 reads the undesigned conflict line with Reload).
- Partial: a2 (SHL-07 on a cited cell), a3 (SHL-09) and d (SHL-08 drawer) are the shell overlays' wiring, not in this row. The version picker is a read-only label ("Version 2 · Run 2"); choosing a prior run lands with checkpoints versioning the workbook. The sheet tabs use the handoff's titles; the server's `SHEETS_1065` titles (02 Adjustments, 03 Form Lines, 04 Allocation) differ and are reconciled with T-05-T27's owner. "Open in Excel" raises a callback; the export route is T-05-T60's.

### Build notes (T-05-T38 rest, TASK-7635, DEC-4630)

- Built: a2, a3 and d on the selected cell. "Cell provenance" opens SHL-09's tray on `<sheet>!<cell>`. "Citations (n)" lists the cell's citations from the server (`WorkbookCellOut.citation_ids`, now filled from review's latest versions), and a document citation opens SHL-08 at its evidence version.
- Version picker: a version is a finished run (`WorkbookOut.versions`), and the newest is the live workbook. An earlier version reads the sheet as it stood when that run finished (`?version=`; review's `values_as_of`) and is read-only. The live sheet now names each cell's writer (`author` from the latest version's source).
- Open: Open in Excel stays T-05-T60; the server's sheet titles differ from the handoff's.
