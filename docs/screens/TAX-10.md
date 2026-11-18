# TAX-10 · Two-year comparison · Feld 2025 Form 1040

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/two-year` (T-08 §5.1); artboards `/components/screens/TAX-10?st=…` |
| Template and host frame | T6 inside T-02 ReturnFrame |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-10 Return - Review - 2-Year Comparison - Feld 2025 Form 1040/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-08 §5.5). Copy keys live in `apps/web/src/screens/TAX-10/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | `feld-two-year-e0` | Samuel Ito | Mon Sep 14, 10:05 AM | planned | AY |
| b | Over threshold | `feld-two-year-e0` | Samuel Ito | Mon 14 Sep 2026, 10:05 AM | planned | AY |
| c | All accepted | `feld-two-year-all-accepted` | Samuel Ito | Mon 14 Sep 2026, 10:07 AM | planned | AY |
| d | Unexplained | `feld-two-year-sep9` | Samuel Ito | Wed Sep 9 | planned | AY |
| e | Agent explaining | `feld-two-year-explaining` | Samuel Ito | Mon 14 Sep 2026, 10:05 AM | planned | AY |
| x1 | Composed DF-04: agents off for this taxpayer | `feld-two-year-agents-off` | Samuel Ito | Mon Sep 14, 10:05 AM | planned | AY |

## Deviations
- DF-39: the Review sub-navigation becomes SheetTabs inside the sheets pane (T-08-T02).
- OQ-2: the threshold popover names the source actually used (checklist v6 > $1,000 and > 10%, else the variance policy).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens SHL-08 with the source lit | SHL-08 | designed (handoff link graph) |
| Opens TAX-05 Leadsheets with line 1a lit | TAX-05 | designed (handoff link graph) |
