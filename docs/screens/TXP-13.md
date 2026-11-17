# TXP-13 · Other entity workpapers · 1120-S · 1120 · 990

| Field | Value |
|---|---|
| Route and params | `/tax/returns/$returnId/review/workpapers` (T-06 §5.1); artboards `/components/screens/TXP-13?st=…` |
| Template and host frame | T6 (per-form frames) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-13 Other entity workpapers - 1120-S - 1120 - 990/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/TXP-13/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | 1120-S · AAA (Bluestem, Accepted, read-only) | `bluestem-1120s` | Samuel Ito | 9:24 AM | built | AY |
| b | 1120 · ASC 740 provision (Ashford 2,257,200) | `ashford-1120` | Samuel Ito | 9:24 AM | built | AY |
| b2 | Exception · unclassified difference (off 1,200) | `ashford-unclassified` | Samuel Ito | 9:24 AM | built | AY |
| c | 990 · Part IX (Lakeshore 4,014,000) | `lakeshore-990` | Olivia Brandt | 9:24 AM | built | AY |
| c2 | 990 · Allocation basis | `lakeshore-990` | Olivia Brandt | 9:24 AM | built | AY |
| c3 | 990 · Building (skeleton) | `lakeshore-990-building` | Olivia Brandt | 9:24 AM | built | AY |
| d | 1120 · from the audit (Granite Peak) | `granite-peak-1120` | Leo Wong | Nov 9, 2026 11:00 AM | built | AY |

## Deviations
- DV-5: a/b/c letters from the README; per-frame toggles composed under DF-08 (T-06-T02, waits on the CLI-03 board).
- DV-6: 1120-S tab is AAA analysis only; Form 7203 note in the footer.
- DV-7: no 1120 M-3 in v1.
- DV-14: TXP-13 d's retained-earnings frame composed from TXP-04 b grammar.
- DV-11: TXP-02's banner reuses TXP-13 d's (DF-08 composed).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens AUD-06 · Final layer | AUD-06 | designed (handoff link graph) |
| Opens AUD-38 · hand-off details | AUD-38 | designed (handoff link graph) |
| Opens SHL-08 · payroll allocation memo | SHL-08 | designed (handoff link graph) |
