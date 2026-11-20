# SHL-22 · Template update

| Field | Value |
|---|---|
| Route and params | O3 overlay `?templateUpdate=1` over the engagement (AUD-02 underlay until ENG-11, K-04) |
| Template and host frame | O3 sheet 500 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-22 Template update/` |
| Epic and tasks | K-03 · SPEC-720; K-03-T04 (TASK-8803); stubs K-03-T08/T09; build per `docs/plan/epics/K-03.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (K-03 §5.5). Copy keys live in `apps/web/src/screens/SHL-22/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures`, never hand-written.

## States
| Letter | Artboard | Persona | Clock (CT) | Figures that must foot | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | Omar Haddad | Thu Oct 1, 10:18 AM | Thu Oct 1, 10:18 AM · Omar Haddad · Harlow & Pike, FS v5 → FS v6 | planned | AY |
| b | Applying | Omar Haddad | Thu Oct 1, 10:20 AM (README: Mon Sep 14; spec wins) | 10:20 AM · 5 of 8 applied | planned | AY |
| c | Updated | Omar Haddad | Thu Oct 1, 10:21 AM (README: Mon Sep 14; spec wins) | 10:21 AM · FS v6 · logged to Activity | planned | AY |
| d | Held | Hannah Leclerc | Thu Oct 1, 4:30 PM | Thu Oct 1, 4:30 PM · Hannah Leclerc · Granite Peak, held until FY2027 | planned | AY |
| e | No permission | Aiden Ward (README: Omar Haddad; spec wins) | Thursday 1 October 2026, 10:18 AM CT | Aiden Ward, Staff · read-only, CSV only | planned | AY |

## AVOID
gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, the word "overwrite", a rollback button, a version-number field (versions are FS v5 / FS v6), changes that touch signed-off rows, auto-applying updates.

## Deviations (chosen truth)
- **b/c date:** the README dates b and c "Mon Sep 14"; the spec and J24 say Thu Oct 1. Truth: Thu Oct 1, 10:20 and 10:21 AM.
- **e viewer:** Aiden Ward (Staff) per the spec; a CSV only.
- Until K-04 builds ENG-11 the overlay opens over the AUD-02 cockpit (K-03-T05, `shl22-underlay.md`); parity masks the underlay.
- A "Removed in vN" row is not drawn (seed has Removed 0); design follow-up `shl22-removed-row.md` (DEC-5805).
- Design follow-up boards **SHL-22f** (Removed in v6 row) and **SHL-22g** (over AUD-02): `docs/design/revisions/K-03-T05/shl22-removed-row.md`, `shl22-underlay.md`.

## Walls and agent
- Walled users: 404, absent from lists, no hidden counts (INV-3, DEC-43).
- The agent never publishes, applies, holds, adopts, signs or raises an exception here (INV-1); attribution "‹person› via Agent" (INV-5).
