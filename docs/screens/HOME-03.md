# HOME-03 · Deadlines calendar

| Field | Value |
|---|---|
| Route and params | `/home/deadlines` (T-08 §5.1); artboards `/components/screens/HOME-03?st=…` |
| Template and host frame | T13 CalendarLayout (list mode T1) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/HOME-03 Deadlines calendar/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-08 §5.5). Copy keys live in `apps/web/src/screens/HOME-03/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Month | `deadlines-e0` | Grace Holloway | Mon Sep 14, 9:24 AM | planned | AY |
| b | List | `deadlines-e0` | Grace Holloway | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| c | Week · Sep 13–19 | `deadlines-e0` | Grace Holloway | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| d | Person · Daniel Reyes | `deadlines-e0-daniel` | Daniel Reyes | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | Rule popover | `deadlines-e0` | Grace Holloway | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| f | +9 more · Sep 15 | `deadlines-e0` | Grace Holloway | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| x1 | Composed: empty filter | `deadlines-empty-filter` | Grace Holloway | Mon Sep 14, 9:24 AM | planned | AY |
| x2 | Composed: postponed item | `deadlines-postponed` | Grace Holloway | Mon Sep 14, 9:24 AM | planned | AY |
| x3 | Composed C-20: flag off | `deadlines-flag-off` | Grace Holloway | Mon Sep 14, 9:24 AM | planned | AY |

## Deviations
- OQ-12: Sep 15 holds 12 here (13 in TPL-13); the scenario is fixed to 12.
- DF-39: the subbar Segmented gains Insights behind its entitlement (I-01 owns the segment).
- The footer cites Knowledge › Standards → KNW-04 section j (K-02).

## Design deltas (T-08-T02, DEC-5601)
Each row is the frame it amends (a handoff screenshot) and the build answer; no new token or colour is introduced.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `HOME-03a.png` Sep 15 cell | 12 items | 12 = 8 × 1065 + 3 × 1120-S + 1 estimate row; TPL-13's 13 does not apply | OQ-12; F-07 R6 |
| `HOME-03a.png` chips | risk shown by tint only | each chip's accessible name and a leading glyph carry the risk in words ("7 days left", "Past due") so risk never relies on colour | non-colour risk cue; F-07 Q1 |
| `HOME-03a.png` done chips | Rao "1040 filed" Sep 11, Harborview "1065 synced" Sep 11 | green on the completion date; the Harborview export is not a deadline | OQ-4 |
| subbar Segmented | four options | five: Insights shown behind its entitlement | DF-39 (I-01 owns the segment) |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens HOME-01 · my work | HOME-01 | designed (handoff link graph) |
| Opens HOME-02 · my approvals | HOME-02 | designed (handoff link graph) |
| Opens HOME-04 · capacity (later wave) | HOME-04 | designed (handoff link graph) |
| Opens TAX-02 · Ridgeline Property Partners, LP · Form 1065 | TAX-02 | designed (handoff link graph) |
| Opens NOT-02 · Thomas & Irene Kowal · IRS CP14 · TY2024 | NOT-02 | designed (handoff link graph) |
| Opens AUD-02 · Northwind Robotics 401(k) Plan · Form 5500 | AUD-02 | designed (handoff link graph) |
| Opens TXT-04 (later wave) · Estate of Walter Thornbury · Form 706 | TXT-04 | designed (handoff link graph) |
| Opens TAX-01 · Q3 2026 individual estimates · Form 1040-ES | TAX-01 | designed (handoff link graph) |
| Opens SIG-01 · envelope E14 · Granite Peak Outdoor Supply · FY2026 FS audit engagement letter | SIG-01 | designed (handoff link graph) |
