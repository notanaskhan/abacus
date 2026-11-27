# SHT-02 · Column and field configurator

| Field | Value |
|---|---|
| Route and params | O2 drawer over SHT-01 (`?column=$columnId`); template mode inside KNW-06 |
| Template and host frame | O2 drawer 480, T12 Fieldset grammar |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHT-02 Column and field configurator/` |
| Epic and tasks | K-03 · SPEC-721; K-03-T04 (TASK-8803); stubs K-03-T08/T09; build per `docs/plan/epics/K-03.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (K-03 §5.5). Copy keys live in `apps/web/src/screens/SHT-02/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures`, never hand-written.

## States
| Letter | Artboard | Persona | Clock (CT) | Figures that must foot | Build | Owner |
|---|---|---|---|---|---|---|
| a | New | Hannah Leclerc | Thu Sep 24, 11:20 AM | Thu Sep 24, 11:20 AM · Hannah Leclerc adds Service period | fixture (K-03-T23) | AY |
| b | Type picker open | Hannah Leclerc | Thursday 24 September 2026, 11:20 AM CT | The 11 column types | fixture (K-03-T23) | AY |
| c | Edit | Hannah Leclerc | Wed Sep 30, 9:50 AM | Wed Sep 30, 9:50 AM · ··· › Edit column… on Service period | fixture (K-03-T23) | AY |
| d | Type change warning | Hannah Leclerc | Thursday 24 September 2026, 11:20 AM CT | Date → Text keeps the values as text | fixture (K-03-T23) | AY |
| e | Blocked delete | Hannah Leclerc | Thursday 24 September 2026, 11:20 AM CT | Service period is used by 2 views and Conclusion | fixture (K-03-T23) | AY |
| f | Not a manager | Simone Baptiste (README: Hannah Leclerc; spec wins) | Thursday 24 September 2026, 11:20 AM CT | Read-only, with a suggest path | fixture (K-03-T23) | AY |

## AVOID
gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, the words Accrual/Arc/ACME/LSA, Fieldguide and its product names (Field Board, Field Auditor, Field Planner, Field Reviewer, Field Financials, Field Orchestrator, AI Actions, Prompt Library, Agent Knowledge), "task" for a to-do, the agent approving/signing/sending anything, boxed form inputs or red required asterisks, a type list other than the 11 types, a client-visibility toggle that is enabled on an internal workpaper, deleting a column that a view or agent column uses, an engagement sheet edit that silently changes the firm template.

## Deviations (chosen truth)
- K-03-T23 (DEC-6034): the drawer is `?ov=column:new[:<afterKey>]` or `?ov=column:<columnId>`. It opens from the header's "··· › Add column…" and "Edit column…". The header "+" is that menu item, so the grid gains no extra column. d and e open on the edit's clock (Wed Sep 30, 9:50 AM), since only a used column warns or refuses. The writes answer 501 until the columns service (K-03-T24) and the screen says so. Template mode (KNW-06) shows the template note and saves with K-03-T52. Closing with changes asks the kit's "Discard changes?". Picking "Agent column" opens `?ov=agent-column:…`, which is unregistered until SHT-04 (K-03-T31). Default is always "Empty". Validation is "End on or after start" for a range.
- **f viewer:** the README lists Hannah Leclerc; the spec says Simone Baptiste or Cole Hart (a manager cannot be the "not a manager" viewer). Truth: the spec — Simone Baptiste.
- Template mode with a Source binding row is a design follow-up (K-03-T05, `docs/design/revisions/K-03-T05/sht02-template-mode.md`).
- Design follow-up board **SHT-02g** Template mode · Source binding: `docs/design/revisions/K-03-T05/sht02-template-mode.md`.

## Walls and agent
- Walled users: 404, absent from lists, no hidden counts (INV-3, DEC-43).
- The agent never publishes, applies, holds, adopts, signs or raises an exception here (INV-1); attribution "‹person› via Agent" (INV-5).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen (K-03-T11/T12).

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/SHT02 Column | SHT-04 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT02 Column | SHL-18 | designed (handoff link graph) |
| tooltip or toast inside kits/SHT02 Column | KNW-06 | designed (handoff link graph) |
