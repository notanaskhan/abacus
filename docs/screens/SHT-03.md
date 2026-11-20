# SHT-03 · Scoping rules editor

| Field | Value |
|---|---|
| Route and params | O3 sheet over KNW-06 (`?rules=1`); read-only over SHT-01 and KNW-03 |
| Template and host frame | O3 sheet 500; C-32 RuleRow |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHT-03 Scoping rules editor/` |
| Epic and tasks | K-03 · SPEC-720; K-03-T04 (TASK-8803); stubs K-03-T08/T09; build per `docs/plan/epics/K-03.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (K-03 §5.5). Copy keys live in `apps/web/src/screens/SHT-03/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures`, never hand-written.

## States
| Letter | Artboard | Persona | Clock (CT) | Figures that must foot | Build | Owner |
|---|---|---|---|---|---|---|
| a | Previewing as Harlow & Pike | Margaret Okonkwo | Thu Oct 1, 8:20 AM | Thu Oct 1, 8:20 AM · Margaret Okonkwo · 6 rules | planned | AY |
| b | Previewing as Granite Peak | Margaret Okonkwo | Thursday 1 October 2026, 8:20 AM CT | A single entity · only rule 6 applies | planned | AY |
| c | Preview off | Margaret Okonkwo | Thursday 1 October 2026, 8:20 AM CT | The rules without results | planned | AY |
| d | Assertion-level variant | Margaret Okonkwo | Thursday 1 October 2026, 8:20 AM CT | Rule 7 shows a row on valuation · High RMM | planned | AY |
| e | Conflict | Margaret Okonkwo | Thursday 1 October 2026, 8:20 AM CT | Rules 2 and 7 show and hide BH-FS-720 · Save blocked | planned | AY |
| f | None | Margaret Okonkwo | Thursday 1 October 2026, 8:20 AM CT | No rules yet | planned | AY |

## AVOID
gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, a rule that the agent evaluates or decides, a hide that deletes prepared or signed-off work, the reference's "If this is selected / Then show" labels verbatim, licensed practice-aid text, publishing from this sheet (publishing is KNW-07).

## Deviations (chosen truth)
- DF-34: SHT-03's numbering is canonical — rules 1–3 and 6 act on steps, 4 on a request group, 5 hides a section.
- Who edits firm-template rules: the QM owner only (DEC-5803).

## Walls and agent
- Walled users: 404, absent from lists, no hidden counts (INV-3, DEC-43).
- The agent never publishes, applies, holds, adopts, signs or raises an exception here (INV-1); attribution "‹person› via Agent" (INV-5).
