# TPL-20 · T18 Sheet specimen · Granite Peak FY2026 · BH-FS-430

| Field | Value |
|---|---|
| Route and params | none (gallery `/components/screens/TPL-20`); artboards `/components/screens/TPL-20?st=…` |
| Template and host frame | T18 cockpit (audit bar 59 · rail 330 · canvas 1036; dock 330) |
| Surface | firm (gallery `/components` only until a consumer epic imports the kit) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-20 T18 Sheet specimen - Granite Peak FY2026 - BH-FS-430 Search for/` |
| Epic and tasks | F-08 · F-08 epic (no SPEC: gallery-only kits); F-08-T01 (TASK-8616); kit and specimen tasks per `docs/plan/epics/F-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: B (F-08 §5.5). Copy keys live in `apps/web/src/screens/TPL-20/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | `tpl20-sep28` | Cole Hart | Mon Sep 28, 5:00 PM | planned | AY |
| b | Agent column running | `tpl20-sep28` | Cole Hart | Sun Sep 27, 6:20 PM | planned | AY |
| c | Row drawer | `tpl20-sep28` | Cole Hart | Monday 28 September 2026, 5:00 PM CT | planned | AY |
| d | Exceptions view | `tpl20-sep28` | Cole Hart | Monday 28 September 2026, 5:00 PM CT | planned | AY |
| e | Locked after review | `tpl20-sep28` | Cole Hart | Thu Oct 1, 4:30 PM | planned | AY |
| f | Empty from template | `tpl20-sep28` | Cole Hart | Thu Sep 24, 10:12 AM | planned | AY |
| g | Dock open | `tpl20-sep28` | Cole Hart | Monday 28 September 2026, 5:00 PM CT | planned | AY |

## Deviations
- Spec time wins over the README's rendered cell where they differ (logged per letter).
- Persona Cole Hart; ?as=cole-hart resolves to a fixture session (F-08-T02).
- Footing: strata ≥ 50,000 (24) 3,286,400 = 1,942,600 + 1,343,800; random (16) 412,300. No '$' in cells, no red row fill.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/Sheet Specimen | SHT-04 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHT-02 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-12 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-17 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-18 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-21 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-15 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-08 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-14 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | AUD-01 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | TPL-21 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | ENG-11 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | TPL-24 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-13 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | SHL-19 | designed (handoff link graph) |
| tooltip or toast inside kits/Sheet Specimen | AUD-36 | designed (handoff link graph) |
