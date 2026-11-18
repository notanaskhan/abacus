# CLS-13 · 1099 / W-9 tracker · Copperleaf 2026

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/information-returns` (C-02 §5.1); artboards `/components/screens/CLS-13?st=…` |
| Template and host frame | T1 IndexList |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-13 1099 W-9 tracker - Copperleaf 2026/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-13/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | September tracking | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon Sep 14, 9:24 AM | planned | AY |
| b | W-9 request batch | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| c | TIN mismatch | `see fixtures/scenarios/CLS-13.ts` | Elena Ruiz | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| d | January · approve batch | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Tue Jan 26, 2027 | planned | AY |
| d2 | January · filed | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | Prior year · 2025 | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| f | Empty | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |

## Deviations
- Personas and clocks per state are in the scenario file. CLS-13c's README viewer cell names the vendor string; the state is Raj Malhotra's.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-01 · Closes | CLS-01 | designed (handoff link graph) |
| Opens SHL-08 · the signed Form W-9 | SHL-08 | designed (handoff link graph) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-13d.png` actions | e-file wording | "Export IRIS file", "Mark filed", "Record acceptance"; no Transmit | R-04, IRIS-001; SPEC-701 AC-18, AC-19 |
| `CLS-13b.png` channel | "Email the vendor a secure W-9 link" selectable | shown unavailable until R-03's link principal | C-02 §2.4 |
| `CLS-13a.png` vendor row | "Elena Ruiz Design" | kept verbatim; the contamination scan allows the exact vendor string | DEC-5508 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-01 · Closes | CLS-01 | designed (handoff link graph) |
| Opens SHL-08 · the signed Form W-9 | SHL-08 | designed (handoff link graph) |
