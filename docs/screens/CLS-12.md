# CLS-12 · Tax hand-off · December 2026 close

| Field | Value |
|---|---|
| Route and params | `/closes/$closeId/tax-handoff` (C-02 §5.1); artboards `/components/screens/CLS-12?st=…` |
| Template and host frame | T6 WorkbookLayout |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-12 Handoff to tax - Copperleaf December 2026 close  2026 Form 1120/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-12/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Ready | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Tue Jan 12, 2027, 2:15 PM | planned | AY |
| b | Not available yet | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Mon Sep 14, 2026 | planned | AY |
| c | Handed off | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Tue 12 Jan 2027, 2:15 PM | planned | AY |
| c2 | TXP-02 · provenance banner | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Tue 12 Jan 2027, 2:15 PM | planned | AY |
| d | Superseded | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Wed Jan 20, 2027 | planned | AY |

## Deviations
- Personas and clocks per state are in the scenario file.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-02 · December 2026 close | CLS-02 | designed (handoff link graph) |
| Opens TXP-10 · this issue | TXP-10 | designed (handoff link graph) |
| Opens CLS-06 · resolved issue history | CLS-06 | designed (handoff link graph) |
| Opens the Fixed Assets workpaper (CLS-04) in a new tab | CLS-04 | designed (handoff link graph) |
