# FIL-02 · Retention & legal hold

| Field | Value |
|---|---|
| Route and params | `/files/retention` (Q-05 §5.1); artboards `/components/screens/FIL-02?st=…` |
| Template and host frame | T1 index list with settings subbar and tabsbar |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/FIL-02 Retention and legal hold/` |
| Epic and tasks | Q-05 · SPEC-711; Q-05-T01 (TASK-8608); stubs Q-05-T03; screens and live swap per `docs/plan/epics/Q-05.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (Q-05 §5.5). Copy keys live in `apps/web/src/screens/FIL-02/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Policies · Felix Andersen | `records_e0` | Felix Andersen | Mon Sep 14, 9:24 AM | planned | AY |
| b | Holds | `records_e0` | Felix Andersen | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| c | Destruction · second approval | `records_e0` | Felix Andersen | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| d | Approve batch… | `records_e0` | Felix Andersen | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| e | Held documents excluded | `fil02e` | Felix Andersen | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| f | Read-only · Samuel Ito | `records_e0` | Samuel Ito | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| g | Policy drawer | `records_e0` | Felix Andersen | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| h | Place hold… | `records_e0` | Felix Andersen | Mon 14 Sep 2026, 9:24 AM | planned | AY |
| i | Batch destroyed | `records_e0` | Felix Andersen | Mon 14 Sep 2026, 9:24 AM | planned | AY |

## Deviations
- DV-1: "Locked · WORM" reads "Locked · sealed" (DF-20) unless the SOC 2 auditor accepts WORM.
- DV-2: the f banner adds 'Partners can also place holds.' (DEC-71, C-10).
- DV-3: c and i add a 'Hold re-check · ‹time›' line and the certificate ID (DF-20).
- OQ-2: a record still under its storage lock is excluded and shows 'Retained until ‹date› (storage lock)' in FIL-01.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens ADM-01 · Settings home | ADM-01 | designed (handoff link graph) |
| Opens FIL-01 · the 3 held documents | FIL-01 | designed (handoff link graph) |
| Opens ADM-07 · Audit log | ADM-07 | designed (handoff link graph) |

## Q-05-T21 (TASK-8827): built
a–i build from `fixtures/scenarios/FIL-02.ts` over the retention summary and policies, the legal
holds list, the destruction batches and approvals, and a policy's versions (Q-05-T13/T15).
- **Deviation:** the "Applies to" counts are not in the policies read; FIL-02g's drawer carries the
  versions. Hold rows read the year and reason; the client and work-item names come with the live
  swap.
