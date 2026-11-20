# SHT-04 · Agent-column editor

| Field | Value |
|---|---|
| Route and params | O3 sheet over SHT-01 (`?agentColumn=$columnId`) |
| Template and host frame | O3 sheet 500 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHT-04 Agent-column editor/` |
| Epic and tasks | K-03 · SPEC-721; K-03-T04 (TASK-8803); stubs K-03-T08/T09; build per `docs/plan/epics/K-03.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (K-03 §5.5). Copy keys live in `apps/web/src/screens/SHT-04/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures`, never hand-written.

## States
| Letter | Artboard | Persona | Clock (CT) | Figures that must foot | Build | Owner |
|---|---|---|---|---|---|---|
| a | Previewing | Simone Baptiste | Fri Sep 25, 2:15 PM | Fri Sep 25, 2:15 PM · Simone Baptiste · 3 rows with citations | planned | AY |
| b | Draft before preview | Simone Baptiste | Friday 25 September 2026, 2:15 PM CT | Nothing has run yet | planned | AY |
| c | Saved and running | Simone Baptiste | Friday 25 September 2026, 2:33 PM | 2:33 PM · saved by Hannah Leclerc 2:31 PM | planned | AY |
| d | Failed preview | Simone Baptiste | Friday 25 September 2026, 2:15 PM CT | @Receiving date is not a column | planned | AY |
| e | Manager view | Hannah Leclerc | Friday 25 September 2026, 2:15 PM CT | Hannah Leclerc · Save and Delete column… | planned | AY |

## AVOID
gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, sparkle or magic-wand glyphs, a run without a preview and a cost estimate, output values outside the four options, a senior's save that bypasses the manager, an exclamation mark in agent text, a green "Save AI Action" button.

## Deviations (chosen truth)
- Save = Manager+; preview and run = Senior+ (the spec over the catalogue's "Manager+").
- The text-output mode ships engine-only and dark (Q7, DEC-5809). Plus the two DF-04 unavailable states.
- Text-output preview block is a design follow-up (K-03-T05, `sht04-text-preview.md`).
- Design follow-up board **SHT-04f** Text output preview: `docs/design/revisions/K-03-T05/sht04-text-preview.md`.

## Walls and agent
- Walled users: 404, absent from lists, no hidden counts (INV-3, DEC-43).
- The agent never publishes, applies, holds, adopts, signs or raises an exception here (INV-1); attribution "‹person› via Agent" (INV-5).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen (K-03-T11/T12).

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/SHT04 Agent | SHL-07 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT04 Agent | SHL-18 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT04 Agent | KNW-11 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT04 Agent | ENG-11 | designed (handoff link graph) |
