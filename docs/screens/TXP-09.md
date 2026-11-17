# TXP-09 · Review › States and PTET · Ridgeline

| Field | Value |
|---|---|
| Route and params | `/tax/returns/$returnId/review/states` (T-06 §5.1); artboards `/components/screens/TXP-09?st=…` |
| Template and host frame | T6 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-09 Review - States and PTET - Ridgeline/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/TXP-09/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Apportionment & PTET (46.0 / 31.5 / 22.5) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| b | Missing factor data (CO Map…) | `ridgeline-run1` | Samuel Ito | 9:24 AM (Run 1) | built | AY |
| c | Payment gap (NY Not paid; Paid 2 of 3) | `ridgeline-run1` | Samuel Ito | 9:24 AM (NY gap) | built | AY |
| d | Nexus | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| e | Approved (Approved · SI · Sep 14) | `ridgeline-m2-accepted` | Samuel Ito | 9:51 AM | built | AY |

## Deviations
- DV-4: the issues badge reads 11, then 10, then 9 (TXP-09 e, TXP-10 d), never 10 twice.
- DV-10: composite and record-election extras not built.
- NYC Recommend opens TAX-15 (T-08) pre-filled; no election recorded here.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens the TXP-10 review point | TXP-10 | designed (handoff link graph) |
| Opens SHL-08 · Form 8825 · the three properties | SHL-08 | designed (handoff link graph) |
| Opens SHL-09 · 08 States!F8 | SHL-09 | designed (handoff link graph) |
| Opens TAX-15 · a planning opportunity for Jonah Feld | TAX-15 | designed (handoff link graph) |
| Opens TXP-12 · state K-1s for Ridgeline GP LLC | TXP-12 | designed (handoff link graph) |
