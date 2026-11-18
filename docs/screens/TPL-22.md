# TPL-22 · T20 Document editor specimen · Granite Peak FY2026 balance sheets · Oct 21

| Field | Value |
|---|---|
| Route and params | none (gallery `/components/screens/TPL-22`); artboards `/components/screens/TPL-22?st=…` |
| Template and host frame | T20 (audit bar 59 · toolbar 44 · TOC 260 · paper 736 · dock 360) |
| Surface | firm (gallery `/components` only until a consumer epic imports the kit) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-22 T20 Document editor specimen - Granite Peak FY2026 balance sheet/` |
| Epic and tasks | F-08 · F-08 epic (no SPEC: gallery-only kits); F-08-T01 (TASK-8616); kit and specimen tasks per `docs/plan/epics/F-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: B (F-08 §5.5). Copy keys live in `apps/web/src/screens/TPL-22/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | `tpl22-oct21` | Hannah Leclerc | Wed Oct 21, 2:10 PM | planned | AY |
| b | Blank | `tpl22-oct21` | Hannah Leclerc | Mon Sep 14, 2026, 9:03 AM | planned | AY |
| b2 | Running | `tpl22-oct21` | Hannah Leclerc | Mon Sep 14, 2026, 9:08 AM | planned | AY |
| c | Stale override | `tpl22-oct21` | Hannah Leclerc | Mon Sep 14, 2026, 9:40 AM | planned | AY |
| d | Comments | `tpl22-oct21` | Hannah Leclerc | Wednesday 21 October 2026, 2:10 PM CT | planned | AY |
| e | Assistant on Note 9 | `tpl22-oct21` | Hannah Leclerc | Wednesday 21 October 2026, 2:10 PM CT | planned | AY |
| f | Shared with the client | `tpl22-oct21` | Hannah Leclerc | Mon Sep 14, 2026, 4:30 PM | planned | AY |

## Deviations
- Spec times win (b 9:03 AM, b2 9:08 AM, c 9:40 AM, f 4:30 PM on Wed Oct 21).
- Balance sheet foots both years (26,410,000 / 23,200,000); inventory lineage 11,906,000 − 486,000 = 11,420,000.
- Builds S54–S55 behind ADR P-59.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/Doc Specimen | FSP-02 | designed (handoff link graph) |
| tooltip or toast inside kits/Doc Specimen | AUD-02 | designed (handoff link graph) |
| tooltip or toast inside kits/Doc Specimen | SHL-12 | designed (handoff link graph) |
| tooltip or toast inside kits/Doc Specimen | SHL-18 | designed (handoff link graph) |
| tooltip or toast inside kits/Doc Specimen | FSP-05 | designed (handoff link graph) |
| tooltip or toast inside kits/Doc Specimen | AUD-06 | designed (handoff link graph) |
