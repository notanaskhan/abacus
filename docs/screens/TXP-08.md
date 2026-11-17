# TXP-08 · Review › Basis · Ridgeline inside / outside basis

| Field | Value |
|---|---|
| Route and params | `/tax/returns/$returnId/review/basis` (T-06 §5.1); artboards `/components/screens/TXP-08?st=…` |
| Template and host frame | T6 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-08 Review - Basis - Ridgeline inside outside basis/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/TXP-08/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | All partners (4 of 5 reconcile) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| b | Partner = Jonah Feld (4,676,125) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| c | Partner = Pell Street II LLC (885,225 vs 913,820) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| d | §754 DecisionCard inline | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| e | §752 shares | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |

## Deviations
- DV-1: README viewer for b reads "Jonah Feld"; the viewer is Samuel Ito.
- DV-3: PRJ-01 links fixture-only until T-09.
- DV-10: the §731 catalogue issue has no design; not built.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens SHL-09 · Inside basis · all partners | SHL-09 | designed (handoff link graph) |
