# CLI-03 · Relationships & household map

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/relationships` (T-06 §5.1); artboards `/components/screens/CLI-03?st=…` |
| Template and host frame | T14 Graph canvas |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-14 Graph canvas specimen - Ridgeline relationships (CLI-03 board not made: T-06-T68)/` |
| Epic and tasks | T-06 · SPEC-702; gate and contract T-06-T01 (TASK-8510); stubs T-06-T05/T07/T08; screens and live swap per `docs/plan/epics/T-06.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-06 §5.4). Copy keys live in `apps/web/src/screens/CLI-03/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default graph (Jonah Feld selected; amber banner) | `ridgeline-graph` | Olivia Brandt | Sep 14, 2026 9:24 AM | built | AY |
| b | List view | `ridgeline-graph` | Olivia Brandt | 9:24 AM | built | AY |
| c | Trust variant (Calloway Family Trust) | `calloway-graph` | Olivia Brandt | 9:24 AM | built | AY |
| d | External node (Not a Brightwater Hale client) | `external-node` | Olivia Brandt | 9:24 AM | built | AY |
| e | Single entity (No relationships yet.) | `single-entity` | Olivia Brandt | 9:24 AM | built | AY |
| f | After Ridgeline approval (K-1s released Sep 15) | `ridgeline-graph-released` | Olivia Brandt | Sep 15, 2026 10:30 AM | built | AY |

## Deviations
- No CLI-03 design board exists (T-06-T68 not made): built from TPL-14 a–f (DEC-32, DF-02); the composed Add relationship… O3 sheet, edit and end wait for the board's sign-off (T-06-T02).
- DV-12: seed names only (Pell Street Ventures LLC, Calloway Family Trust, Jonah Feld), never the template board's placeholders.
- The graph never appears in the portal (INV-4).
