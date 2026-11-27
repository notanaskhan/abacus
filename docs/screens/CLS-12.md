# CLS-12 · Tax hand-off · December 2026 close

| Field | Value |
|---|---|
| Route and params | `/closes/$closeId/tax-handoff` (C-02 §5.1); artboards `/components/screens/CLS-12?st=…` |
| Template and host frame | O3 SheetModal over CLS-02 (C-02-T48; the handoff names O3) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-12 Handoff to tax - Copperleaf December 2026 close  2026 Form 1120/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | live (C-02-T48: a, c, c2, d; b is CLS-02's menu item) |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-12/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Ready | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Tue Jan 12, 2027, 2:15 PM | live | AY |
| b | Not available yet | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Mon Sep 14, 2026 | live | AY |
| c | Handed off | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Tue 12 Jan 2027, 2:15 PM | live | AY |
| c2 | TXP-02 · provenance banner | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Tue 12 Jan 2027, 2:15 PM | live | AY |
| d | Superseded | `see fixtures/scenarios/CLS-12.ts` | Priya Raman | Wed Jan 20, 2027 | live | AY |

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


## Data and states (C-02-T48, DEC-6031)

| State | Data condition | Read / write |
|---|---|---|
| a | December close locked Jan 11, 2027; `status` ready, TB v1, balanced; target 2026 Form 1120-S, CCH Axcess Tax, Olivia Brandt and Samuel Ito; five schedules and three items on | `GET /v1/closes/{id}/tax-handoff` |
| b | the August close: `not_available` with the reason; CLS-02's "Handoff to tax…" menu item disabled with that reason (`statusItems` reads the hand-off when `closes.tax_handoff` is on) | as a |
| c | after "Hand off": one POST with the version seen, the toggled schedules and items; the toast "Handed off to 2026 Form 1120-S · n tax issues created" | `POST …/tax-handoff` |
| c2 | `handed_off`: TXP-02's provenance banner previewed with `handed_off_by` and `handed_off_at`; Hand off closed | as a |
| d | reopened after the hand-off (`superseded_on_next`, `reopened_at`): the supersede banner names the tax team | as a |

Additive read fields (C-02-T48): `target_form`, `target_tax_year`, `target_engine`, `target_preparer`, `target_reviewer`, `handed_off_by`, `handed_off_at`, `reopened_at`.

Links: "View close ›" → CLS-02; the tax issues → TXP-10; an item → CLS-06; a schedule → CLS-04 in a new tab (`rel="noopener noreferrer"`).

**Deviations (C-02-T48).** (1) The route `/closes/$closeId/tax-handoff` renders CLS-02 with the sheet open; ✕ and Escape return to CLS-02. (2) Schedule detail lines are copy around the read's figures; deferred revenue and accrued payroll carry no figures in the read. (3) "Entries — 12 monthly batches carried as history" is copy, not a count from the read.
