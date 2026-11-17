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

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens the checkpoint in SHL-16 | SHL-16 | designed (handoff link graph) |
| Opens SHL-09 · account 4510 → Schedule K line 18a | SHL-09 | designed (handoff link graph) |
| Opens TXP-05 · Analysis of Net Income | TXP-05 | designed (handoff link graph) |
| Opens FIL-01 · 2024 Form 1065 · Schedule L line 21 · 5,960,000 | FIL-01 | designed (handoff link graph) |
| Opens TXP-02 · Financials · account 3100 Partner contributions | TXP-02 | designed (handoff link graph) |
| Opens TXP-11 · workpaper · 07 M-2!C9 | TXP-11 | designed (handoff link graph) |
| Opens the TXP-10 issue | TXP-10 | designed (handoff link graph) |
