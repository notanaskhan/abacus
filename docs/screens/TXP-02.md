# TXP-02 · Review › Financials (TB → TTB) · Ridgeline 2025 Form 1065

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/financials` (`?view=account|line&statement=full|balance_sheet|income_statement&filter=unmapped`) |
| Template and host frame | T6 workbook layout: control bar 44 · tally strip 52 · full-width statement pane |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-02 Review - Financials -TB  TTB- - Ridgeline 2025 Form 1065/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Olivia Brandt (Tax Senior, preparer) |
| Flags | `tax.entity_workspace`; mapper suggestions `tax.entity_agents` |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | By Account · Full TB | Run 2 TB: 28 accounts PY, UTB, AJE, RJE, ATB, TJE, TTB; tallies tie | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only, **lock proposed** | planned |
| a2 | Cell provenance | SHL-09 on account 2050: `01 Trial Balance!I18 = F18+G18+H18` → (94,000) | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| a3 | AJE-1 | O2 drawer: AJE-1 18,500 accrual from the Cook County second-installment bill, "Approved by Samuel Ito · Sep 9" | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| b | Balance Sheet | `statement=balance_sheet`: total assets 17,914,500 = liabilities 11,048,300 + capital 6,866,200 | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| c | Income Statement | `statement=income_statement` | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| d | Grouped by Form 1065 Line | `view=line`: Schedule L, Form 8825 (by property), Schedule K, M-2 and M-3 subtotals from server totals | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| e | Unmapped | Run 1 snapshot: account 1300 "Map…", Unmapped 1 (Check), sync chip disabled "Map every account first" | Mon Sep 14, 2026, 9:24 AM CT | Sep 8 snapshot | D (blocking) · C report-only | planned |
| e2 | Line picker | Line picker open over the published TY2025 1065 form-line set | Mon Sep 14, 2026, 9:24 AM CT | Sep 8 snapshot | D (blocking) · C report-only | planned |
| f | Building | `import_trial_balance` running: tallies Pending, rows skeletons | Mon Sep 14, 2026, 9:24 AM CT | run active | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-02 a, a2, a3, b, c, d, e, e2, f` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/trial-balance`
- `GET /v1/tax-returns/{id}/trial-balance/tallies`
- `GET /v1/tax-returns/{id}/journal-entries`
- `GET /v1/tax-returns/{id}/workbook/cells/{address}`
- `GET /v1/form-lines?form=1065&tax_year=2025&q=`
- `POST /v1/tax-returns/{id}/mappings`
- `POST /v1/proposals/{id}/approve (P-04)`
- `GET /v1/tax-returns/{id}/workbook/export.xlsx?sheet=01`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Amount | SHL-09 (workbook address) | planned |
| AJE-1 amount | O2 drawer, source SHL-08 | planned |
| Map… | line picker (O1 300) then SHL-10 | planned |
| Sync chip | TAX-09 (T-01) | planned |

## Notes

TB grammar: "$" on every cell (the only TXP screen that uses it). 28 accounts (QBO's 27 plus tax-only 4510-T); every column foots to $0; 17,914,500 = 11,048,300 + 6,866,200; capital 5,960,000 + 250,000 + 1,256,200 − 600,000 = 6,866,200. The README's "Links: none found" is wrong; the spec's outbound links are authoritative.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-02 acceptance: <criterion>".
