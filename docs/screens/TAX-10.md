# TAX-10 · Two-year comparison · Feld 2025 Form 1040

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/two-year` (T-08 §5.1); artboards `/components/screens/TAX-10?st=…` |
| Template and host frame | T6 inside T-02 ReturnFrame |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-10 Return - Review - 2-Year Comparison - Feld 2025 Form 1040/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | fixture (T-08-T22, DEC-5938; live over `GET …/two-year` behind `tax.two_year`) |

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
- T-08-T22 (DEC-5938): built a–e and x1 at `/tax-returns/$returnId/review/two-year`; copy in `screens/TAX-10/copy.ts`; fixtures from `two_year_slice.py` (`seed/scenario.tax10.json`). "7 of 8" is a value card (no tally word); citation chips are tags until SHL-08 lands; the line label links to TAX-05 once it is built.
- DF-39: the Review sub-navigation becomes SheetTabs inside the sheets pane (T-08-T02).
- OQ-2: the threshold popover names the source actually used (checklist v6 > $1,000 and > 10%, else the variance policy).

## Design deltas (T-08-T02, DEC-5601)
Each row is the frame it amends (a handoff screenshot) and the build answer; no new token or colour is introduced.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `TAX-10a.png` Review sub-navigation | pill row | SheetTabs inside the sheets pane ("2-Year Comparison" tab registered hidden by T-04 until the flag is on) | DF-39 |
| composed DF-04 | no frame | agents off for this taxpayer or AI unavailable: "Explain…" disabled with the DF-04 copy, "Edit" enabled, acceptance unchanged | DF-04; SPEC-710 AC-23 |
| `TAX-10a.png` threshold popover | "> $1,000 and > 10% · 1040 Review Checklist v6" | names the source actually used (checklist parameter or the variance policy row) and its version | OQ-2 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens SHL-08 with the source lit | SHL-08 | designed (handoff link graph) |
| Opens TAX-05 Leadsheets with line 1a lit | TAX-05 | designed (handoff link graph) |
