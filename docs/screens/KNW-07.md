# KNW-07 · Template versions and rollout — BH Audit Methodology · FS

| Field | Value |
|---|---|
| Route and params | /knowledge/templates/$templateId |
| Template and host frame | T1 index (5 tiles + Versions and Rollout panes) + O3 publish / dry-run sheets + Dialog 440 + O2 drawer 480 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/KNW-07 Template versions and rollout - BH Audit Methodology - FS/` |
| Epic and tasks | K-03 · SPEC-720; K-03-T04 (TASK-8803); stubs K-03-T08/T09; build per `docs/plan/epics/K-03.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (K-03 §5.5). Copy keys live in `apps/web/src/screens/KNW-07/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures`, never hand-written.

## States
| Letter | Artboard | Persona | Clock (CT) | Figures that must foot | Build | Owner |
|---|---|---|---|---|---|---|
| a | Published · actions set | Margaret Okonkwo | Thu Oct 1, 9:45 AM | Thu Oct 1, 9:45 AM · rollout not started | planned | AY |
| b | Draft · publish | Margaret Okonkwo | Thu Oct 1, 9:36 AM | 9:36 AM · the publish sheet | planned | AY |
| c | Start rollout | Margaret Okonkwo | Thu Oct 1, 9:45 AM | The confirmation · Omar Haddad and Laura Kemp notified | planned | AY |
| d | Rollout in progress | Margaret Okonkwo | Thu Oct 1, 10:25 AM | 10:25 AM · 1 of 3 applied · Granite Peak held | planned | AY |
| e | Dry run | Margaret Okonkwo | Thu Oct 1, 9:45 AM | Harlow & Pike · SHL-22 read-only | planned | AY |
| f | Deprecate FS v5 | Margaret Okonkwo | Thu Oct 1, 9:45 AM | For new work · live engagements keep it | planned | AY |
| g | Used by | Margaret Okonkwo | Thu Oct 1, 9:45 AM | FS v5 · 6 live + A20 archived | planned | AY |

## AVOID
gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, applying an update to an engagement from this screen, rollout to archived engagements, an "Update" button inside the dry run, the word "Superseded" on FS v5, blue notice banners.

## Deviations (chosen truth)
- "Superseded" only for FS v4. No Update button in the dry run; no apply from this screen.
- Rows filtered by `visible()` with no hidden count (DEC-5806).
- Icon map: `docs/design/revisions/K-03-T05/icons.md`.

## Walls and agent
- Walled users: 404, absent from lists, no hidden counts (INV-3, DEC-43).
- The agent never publishes, applies, holds, adopts, signs or raises an exception here (INV-1); attribution "‹person› via Agent" (INV-5).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen (K-03-T11/T12).

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/KNW07 Rollout | ENG-11 | designed (handoff link graph) |
| tooltip or toast inside kits/KNW07 Rollout | KNW-01 | designed (handoff link graph) |
| tooltip or toast inside kits/KNW07 Rollout | KNW-06 | designed (handoff link graph) |
