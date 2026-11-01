# SPEC-641 · Designed workpaper cell addresses (EBP-01 to EBP-09)

| Field | Value |
|---|---|
| Status | accepted (A-05-T09, TASK-2906, 2026-11-01) |
| Decisions | DEC-36, P-07 (ADR-160 clause 13), DEC-1954 |
| Epic | A-05 (§4.1, R12); consumers A-04's cell store, C3 anchors, C4 citation locators, AUD-06 |

## 1. Summary
A designed workpaper's cell has one address, the same in the app, the field history, a citation
and the Open-in-Excel export: `Sheet!A1`, or `'Sheet name'!A1` when the sheet's title has a space,
and a rectangular range `A1:B3` that names each cell in row-major order.

## 2. The scheme
- A paper registers a `DesignedLayout` (`workpapers.api.register_designed_layout`): its kind, its
  code, its sheets in order (each a cell-store `sheet_key` and the title Excel shows) and its
  named anchors. Registration refuses duplicate titles or keys and any anchor that does not
  resolve.
- The paper's first sheet has key `main` and the paper's code as its title (`EBP-04`); a second
  sheet has its own key and title (`participant_data`, `EBP-04 Participant data`).
- A cell's key in the store is its A1 reference on its sheet (`C14`); the field history's key is
  `cell_ref(sheet_key, cell_key)` (`C14` on `main`, `participant_data!F12` elsewhere).
- Columns A to ZZ, rows 1 to 9999; a range holds at most 400 cells. Code parses addresses
  (`workpapers/layouts.py`); a spreadsheet's own formulas are never evaluated (ADR-110).

## 3. The export
A designed paper's XLSX export writes a cover sheet, then each layout sheet under its title with
every cell at its own address. Cells on keys outside the layout keep the list layout. The export
stays byte-stable (DEC-44): fixed workbook properties and sorted parts.

## 4. Seeded anchors (EBP-04)
| Anchor | Address | Cells |
|---|---|---|
| Contributions total | `EBP-04!C14` | `main` C14 |
| Dec 26 business-day count | `EBP-04!F31` | `main` F31 |
| Participant deferrals | `'EBP-04 Participant data'!F12:F15` | `participant_data` F12–F15 |

## 5. Acceptance
- Every anchor of every registered layout resolves to exactly one cell per address in the export
  (`tests/unit/workpapers/test_a05t09_designed_layouts.py`).
- The nine papers' rail rows appear on an EBP audit's cockpit with C2 `audit_section` codes and on
  no other audit (`tests/integration/backfill/test_a05t09_ebp_rail.py`).
