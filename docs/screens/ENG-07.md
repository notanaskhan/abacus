# ENG-07 · Season setup / roll-forward

| Field | Value |
|---|---|
| Route and params | `/engagements/season` (T-08 §5.1); artboards `/components/screens/ENG-07?st=…` |
| Template and host frame | T6 WorkbookLayout |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-07 Season setup roll-forward/` |
| Epic and tasks | T-08 · SPEC-710; T-08-T01 (TASK-8600); stubs T-08-T04; screens and live swap per `docs/plan/epics/T-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: C (T-08 §5.5). Copy keys live in `apps/web/src/screens/ENG-07/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Draft cohort under review | `season-ty2025-jan12` | Samuel Ito | Mon Jan 12, 10:15 AM | planned | AY |
| b | Approved | `season-ty2025-cohort5-approved` | Samuel Ito | Mon 12 Jan 2026, 10:21 AM | planned | AY |
| c | Executing · cohort 3 | `season-ty2025-cohort3-executing` | Samuel Ito | Mon 12 Jan 2026, 10:15 AM | planned | AY |
| d | Exceptions | `season-ty2025-jan12` | Samuel Ito | Mon 12 Jan 2026, 10:15 AM | planned | AY |
| e | Agent asks | `season-ty2025-jan12` | Samuel Ito | Mon 12 Jan 2026, 10:15 AM | planned | AY |
| x1 | Composed DF-04: planner unavailable (exceptions only) | `season-ty2025-agents-off` | Samuel Ito | Mon Jan 12, 10:15 AM | planned | AY |
| x2 | Composed C-20: flag off | `season-flag-off` | Samuel Ito | Mon Jan 12, 10:15 AM | planned | AY |

## Deviations
- OQ-8: the running pill reads 'Creating engagements for cohort 3 · approved by Samuel Ito' (attribution; T-08-T02).
- The provenance chip to WB-06 is a planned link until W-03; 'View run ›' to WB-09 is live.
- Letters and §7216 consents are separate documents (R-01 #1).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens WB-06 · Season Setup Planner | WB-06 | designed (handoff link graph) |
| Opens WB-09 · run trace | WB-09 | designed (handoff link graph) |
| Opens BND-02 · draft binder preview | BND-02 | designed (handoff link graph) |
| Opens SIG-01 | SIG-01 | designed (handoff link graph) |
| Opens CLI-02 · client record | CLI-02 | designed (handoff link graph) |
