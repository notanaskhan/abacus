# TXP-03 · Review › Fixed Assets · Ridgeline depreciation register

| Field | Value |
|---|---|
| Route and params | `/tax/returns/$returnId/review/fixed-assets` (T-06 §5.1); artboards `/components/screens/TXP-03?st=…` |
| Template and host frame | T6 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-03 Review - Fixed Assets - Ridgeline depreciation register/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/TXP-03/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Register (roof flag; Larimer bonus Check) | `ridgeline-e0` | Samuel Ito | Sep 14, 2026 9:24 AM | built | AY |
| a2 | Asset detail drawer (O2) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| b | By property (land 3,600,000; 733,500 to 8825) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| c | Bonus check resolved (contract Feb 3, 2025) | `ridgeline-bonus-resolved` | Samuel Ito | 10:12 AM | built | AY |
| d | Dispositions (EmptyState, §1245/§1250) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| e | Signed off (✓ SI) | `ridgeline-signed-off` | Samuel Ito | 10:30 AM | built | AY |

## Deviations
- DV-3: PRJ-01 links fixture-only until T-09; live build hides them behind `allowed_actions`.
- Never label the Elm Street roof "QIP" (T-06-T04 copy ban).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens TXP-02 · rows 1600, 1650 and 5600 | TXP-02 | designed (handoff link graph) |
| Opens TXP-10 with the bonus issue selected | TXP-10 | designed (handoff link graph) |
| Opens SHL-09 · 02 Fixed Assets!E8 | SHL-09 | designed (handoff link graph) |
| Opens SHL-08 · Larimer_Parking_Invoice_Feb2025.pdf | SHL-08 | designed (handoff link graph) |
