# TAX-05 · Return › Review — Review preset (Feld 2025 Form 1040)

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | T3 Review preset (452 × 3) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-05 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P0 |
| Manifest status | planned |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Default (K-1 beside Sch E – K-1 matrix, CY + 2024, box 5 ↔ Interest Income lit) | planned |
| b | Approved (Statement A "✓ 1", Review 37→36, toast "Approved for manager review · Samuel Ito") | planned |
| c | Flagged (⚑ 1 opens TAX-06 with 18A selected) | planned |
| d | Worksheets tab (TXI-01 fields "Sch E p2 — Ridgeline", ✓ KO ✓ OB) | planned |
| e | All approved (green-tint banner "All 41 documents approved at manager level · Samuel Ito"; "Request final approval…" blocked by Draft K-1) | planned |
| f | Loading | planned |
| loading | skeleton per the handoff | planned |
| not allowed | walled or out of scope: 404 (INV-3) | planned |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| Opens TXI-02 (later) | TXI-02 | planned (handoff link; T-04-T08 onward wires it) |
| Box 18A is not on the worksheet · open issue in TAX-06 | TAX-06 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
DF-34: Review 37 = 41 − 4, then 36 (the catalogue's "38 → 37" is wrong). K-1 status pill → TXI-02 (behind `tax.individual_workpapers`). Matrix grammar is the E4 leadsheet/fields grammar

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
