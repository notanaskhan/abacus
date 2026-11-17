# TXP-04 · Review › M-1/M-3 and Schedule M-2 · Ridgeline

| Field | Value |
|---|---|
| Route and params | `/tax/returns/$returnId/review/m1-m3` and `/review/m2` (T-06 §5.1); artboards `/components/screens/TXP-04?st=…` |
| Template and host frame | T6 (two Group B tab frames) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-04 Review - M-1M-3 and Schedule M-2 - Ridgeline/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/TXP-04/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | M-3 (one permanent row 6,200) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| a′ | M-1 reference toggle (file `TXP-04ap.png`) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| b | M-2 as drafted (6,860,000 vs 6,866,200) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| c | With proposed fix (tie) | `ridgeline-e0` | Samuel Ito | 9:24 AM | built | AY |
| d | Accepted (Approved by Samuel Ito · 9:51 AM) | `ridgeline-m2-accepted` | Samuel Ito | 9:51 AM | built | AY |

## Deviations
- M-1 and M-3 never both marked filed; TAX-11 renders only M-3.
