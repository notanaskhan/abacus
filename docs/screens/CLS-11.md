# CLS-11 · Ledger console · Copperleaf QuickBooks Online

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/entities/$entityId/ledger` (C-02 §5.1); artboards `/components/screens/CLS-11?st=…` |
| Template and host frame | T2 record cockpit |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-11 GL sync console - Copperleaf - QuickBooks Online/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-11/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Connected | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon Sep 14, 9:24 AM | planned | AY |
| a2 | Sync events | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| b | Posted | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:22 AM | planned | AY |
| b2 | Batch drawer | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| c | Needs attention | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:03 AM | planned | AY |
| d | Needs reauth | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:14 AM | planned | AY |
| d2 | Request reconnect | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | Closing date conflict | ``fixtures/scenarios/CLS-11.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:21 AM | planned | AY |

## Deviations
- Personas and clocks per state are in the scenario file (CLS-07 c, c2, d are Priya Raman's; the README's viewer column names Raj).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-02 · August 2026 close | CLS-02 | designed (handoff link graph) |
| Opens WB-11 · QuickBooks Online integration detail | WB-11 | designed (handoff link graph) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-11a.png` Write scope row | "Journal entries · recategorizations · attachments" | "Journal entries · closing date" | W1 v1 writes only JEs and the closing date (ADR-344 §1; SPEC-700 Q2) |
| `CLS-11a.png` Authorized by | Mar 9, 2026 | Mar 9, 2026 is the write grant; the connection is Mar 4, 2026 (POR-16e) | seed contradiction settled (DEC-5508) |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-02 · August 2026 close | CLS-02 | designed (handoff link graph) |
| Opens WB-11 · QuickBooks Online integration detail | WB-11 | designed (handoff link graph) |
