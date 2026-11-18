# TPL-23 · T21 Analytics dashboard specimen · Insights › Client responsiveness · Oct 1

| Field | Value |
|---|---|
| Route and params | none (gallery `/components/screens/TPL-23`); artboards `/components/screens/TPL-23?st=…` |
| Template and host frame | T21 home |
| Surface | firm (gallery `/components` only until a consumer epic imports the kit) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-23 T21 Analytics dashboard specimen - Insights - Client responsiven/` |
| Epic and tasks | F-08 · F-08 epic (no SPEC: gallery-only kits); F-08-T01 (TASK-8616); kit and specimen tasks per `docs/plan/epics/F-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: B (F-08 §5.5). Copy keys live in `apps/web/src/screens/TPL-23/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | `tpl23-oct1` | Margaret Okonkwo | Thu Oct 1, 9:30 AM | planned | AY |
| b | Hover · Past due now | `tpl23-oct1` | Margaret Okonkwo | Thursday 1 October 2026, 9:30 AM CT | planned | AY |
| c | Filtered to one client | `tpl23-oct1` | Margaret Okonkwo | Thursday 1 October 2026, 9:30 AM CT | planned | AY |
| d | Loading | `tpl23-oct1` | Margaret Okonkwo | Thursday 1 October 2026, 9:30 AM CT | planned | AY |
| e | Restricted | `tpl23-oct1` | Felix Andersen | Thursday 1 October 2026, 9:30 AM CT | planned | AY |
| f | Flag off | `tpl23-oct1` | Margaret Okonkwo | Thursday 1 October 2026, 9:30 AM CT | planned | AY |

## Deviations
- Persona Margaret Okonkwo; e is Felix Andersen (counts only).
- Footing: 2,804 + 1,432 + 214 = 4,450; buckets 78 + 46 + 44 + 34 + 12 = 214 (F-08-T03).
- No peer benchmark (D6).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/Dash Specimen | BND-04 | designed (handoff link graph) |
| tooltip or toast inside kits/Dash Specimen | ENG-12 | designed (handoff link graph) |
| tooltip or toast inside kits/Dash Specimen | CLI-02 | designed (handoff link graph) |
