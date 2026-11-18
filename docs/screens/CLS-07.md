# CLS-07 · Adjustments & thresholds · Copperleaf August 2026

| Field | Value |
|---|---|
| Route and params | `/closes/$closeId/adjustments` (C-02 §5.1); artboards `/components/screens/CLS-07?st=…` |
| Template and host frame | T6 WorkbookLayout |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-07 Adjustments and thresholds - Copperleaf August 2026/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-07/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Awaiting approval | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon Sep 14, 9:24 AM | planned | AY |
| a2 | Batch approve · SHL-10 | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| b | Batch approved | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:31 AM | planned | AY |
| c | Priya’s view | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:12 AM | planned | AY |
| c2 | Post confirm | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:21 AM | planned | AY |
| d | Posted | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 10:22 AM | planned | AY |
| e | Failed post | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| f | Policy acceptance · ADM-04 enabled — off at Brightwater Hale | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| g | Attest client — not Copperleaf | ``fixtures/scenarios/CLS-07.ts` state` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | planned | AY |

## Deviations
- Personas and clocks per state are in the scenario file (CLS-07 c, c2, d are Priya Raman's; the README's viewer column names Raj).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens SHL-08 · Receiving log — Aug 28 | SHL-08 | designed (handoff link graph) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-07c.png` row state | no Rejected row | a Rejected row: soon pill "Rejected", the reason, and the CLS-06 issue link | DF-23; SPEC-700 AC-11 |
| `CLS-07g.png` footer | implies posting for the attest client | no Post control at all; "Send to client for approval…" only; rows read "Client approved" then "Recorded by ‹client›" | DEC-69, ADR-344 §4 |
| `CLS-07a.png` primary without W1 | "Post 4 approved…" | "Export approved entries…" when `posting_enabled` is off; rows reach "Recorded in ledger" | DF-19; SPEC-700 AC-20 |
| `CLS-07f.png` | "Accepted by Policy" sub-line | fixture-only frame in `/components`; never live | DEC-53, ADR-187 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens SHL-08 · Receiving log — Aug 28 | SHL-08 | designed (handoff link graph) |
