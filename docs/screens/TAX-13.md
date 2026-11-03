# TAX-13 · Extensions, estimates and payments

| Field | Value |
|---|---|
| Route and params | `/tax-returns/extensions` · `?tax_year=` `?tab=extensions\|estimates\|payments` `?segment=open\|filed\|likely` `?tile=` `?q=` · `?ov=extend:<returnIds>` (SheetModal) · `?ov=mark-filed:<extensionId>` |
| Template and host frame | T6 WorkbookLayout (F-06-T18) with the RecordHeader index variant ("‹ All returns") · `Wave 3 - Tax Returns.dc.html#tax13` |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-13 Extensions- estimates and payments - TY2025/` (README.md, spec.md; no revision.md) |
| Epic and tasks | T-03 · stubs T02 (`docs/contracts/tax-extensions-estimates.md`) · service T07 · a, b, c T11 · d, e T16 · E2E and parity T17 |
| Manifest status | planned until T-03-T11 (fixture) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | samuel-ito | Mon Sep 14, 2026, 9:24 AM CT | 161 extended (79 open + 82 filed) + 2 likely; 10 named rows; Ridgeline and Harborview due tomorrow ("1 day") | fixture (T11) |
| b | samuel-ito | same | TY2026 Q3 installments for 7 schedules: Paid 2 · Scheduled 1 · Awaiting confirmation 2 = 5 due; Not required 2 | fixture (T11) |
| c | samuel-ito | same | Likely segment: Lakeshore 990 "Prepare 8868…"; Thornbury 706 "Prepare 4768…" disabled (G1/G3 unmet) | fixture (T11) |
| d | samuel-ito | Fri Apr 10, 2026, 9:20 AM | 38 extended, 123 likely; Feld, Shah, Varga selected; Extend 3 returns sheet open | fixture (T16) |
| e | samuel-ito | Tue Apr 14, 2026, 4:05 PM | 149 extended; Feld Filed (ack pending); Varga Rejected IND-031-04 | fixture (T16) |
| Payments | samuel-ito | Sep 14 | DF-08 union composed from extension payments, PTET and paid installments, or hidden | composed (DEC-32) |
| not-allowed | kevin-osei | Apr 10 | No reviewer function on d: "Submit for approval" replaces approve-and-send | composed |

## API
| Read or write | Endpoint | Shape | Matrix action | Notes |
|---|---|---|---|---|
| read | `GET /v1/tax/extensions` | `ListPage[ExtensionRowOut]` | `filing_extension.read` | Tallies are visible rows only (DEC-43) |
| read | `GET /v1/tax/estimates` | `ListPage[EstimateRowOut]` | `estimate_schedule.read` | — |
| read | `GET /v1/tax/payments` | `ListPage[PaymentRowOut]` | `filing_extension.read` | DF-08 |
| write | `POST /v1/tax/extensions:approve-and-request` | `ApproveAndRequestOut` | `filing_extension.approve_payment` | reviewer function only |
| write | `POST /v1/tax/extensions:prepare` · `:submit-for-approval` | `ExtensionBatchOut` | `filing_extension.prepare` | 409 `gate_unmet` |
| write | `PATCH /v1/tax/extensions/{id}` | `ExtensionOut` | `filing_extension.mark_filed` · `.flag_likely` | If-Match |
| write | `POST …/confirmation-requests` | `ConfirmationRequestOut` | `filing_extension.confirmation_send` · `estimate_schedule.confirmation_send` | sent on the click |
| export | `GET …/export.xlsx` | bytes | `tax_schedule.export` | fresh MFA |

## Status
`filing_extension`, `estimate_installment`.

## Copy
Verbatim from spec.md: "‹ All returns", "Extensions & estimates", "Extensions", "Estimates", "Payments", "Open on extension", "Filed", "Likely to extend", "Open in Excel", "Extend selected…", "Search clients", "Extended returns", the tally labels and column headers; "Opens after acceptance (CLI-07) and a signed letter (G3)"; "4768 extends time to file only; estate tax is still due Nov 2".

## Deviations
- DV-TAX-13-1 (DEC-2201): the sheet button reads **"Send confirmation requests"**, not the spec's "Send confirmation tasks" (DEC-14: "task" is banned for assignable work).
- DV-TAX-13-2: POR-10's "task preview" is the confirmation **request item** in the return's binder (R-03 reads it). The "Client confirmation ○" link opens that request.
- DV-TAX-13-3: links to TAX-06 and TXT-04 are **planned**. They are hidden in production and show "Not built yet" in dev and fixture builds.
- DV-TAX-13-4: cells keep the spec's grammar, with no "$".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| ‹ All returns; bulk Extend… | TAX-01 | live |
| Client cell | TAX-02 | live |
| Ext. form and Paid cells | SHL-08 | live |
| Thornbury's disabled tooltip | CLI-07 | live |
| Client confirmation ○ (the confirmation request) | POR-10 | live |
| Return issues | TAX-06 | planned, hidden in production (DV-TAX-13-3) |
