# TPL-24 · T22 Office add-in pane specimen · Excel add-in on the Granite Peak AP leadsheet

| Field | Value |
|---|---|
| Route and params | none (gallery `/components/screens/TPL-24`); artboards `/components/screens/TPL-24?st=…` |
| Template and host frame | T22 (drawn host + 350 pane) |
| Surface | firm (gallery `/components` only until a consumer epic imports the kit) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-24 T22 Office add-in pane specimen - Excel add-in on the Granite Pe/` |
| Epic and tasks | F-08 · F-08 epic (no SPEC: gallery-only kits); F-08-T01 (TASK-8616); kit and specimen tasks per `docs/plan/epics/F-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: B (F-08 §5.5). Copy keys live in `apps/web/src/screens/TPL-24/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default · Link | `tpl24-sep30` | Cole Hart | Wed Sep 30, 2:15 PM | planned | AY |
| b | Tickmarks | `tpl24-sep30` | Cole Hart | Wednesday 30 September 2026, 2:15 PM CT | planned | AY |
| c | Sign-off | `tpl24-sep30` | Cole Hart | Mon Sep 14, 2026, 2:21 PM | planned | AY |
| d | Changed after sign-off | `tpl24-sep30` | Cole Hart | Mon Sep 14, 2026, 2:40 PM | planned | AY |
| e | Offline | `tpl24-sep30` | Cole Hart | Wednesday 30 September 2026, 2:15 PM CT | planned | AY |
| f | Word host | `tpl24-sep30` | Hannah Leclerc | Mon Oct 26, 4:15 PM | planned | AY |
| g | Signed out | `tpl24-sep30` | Cole Hart | Wednesday 30 September 2026, 2:15 PM CT | planned | AY |

## Deviations
- Spec times win (c 2:21 PM, d 2:40 PM Sep 30; f Mon Oct 26, 4:15 PM).
- Leadsheet 3,962,400 + 217,600 = 4,180,000; exactly two Word incoming changes (F-08-T03).
- Host chrome is greys only.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/Addin Specimen | SHL-08 | designed (handoff link graph) |
| tooltip or toast inside kits/Addin Specimen | SHT-01 | designed (handoff link graph) |
| tooltip or toast inside kits/Addin Specimen | FSP-01 | designed (handoff link graph) |

## Built (F-08-T19, DEC-5928)

Gallery specimen at `/components/screens/TPL-24?st=a…g` (`apps/web/src/gallery/specimens/TPL-24`), on the Granite Peak AP leadsheet seed (`fixtures/seed/granite-peak-fy2026-ap-leadsheet.ts`, footed by `insights-addin.foot.test.ts`). The drawn hosts are `HostWindow`, `ExcelGrid` and `WordPage` from the specimens entry (`@abacus/ui/specimens`; greys only: band-hd, nav-fill, nested, chip, surface-deep), with the C-39 `AddinChrome` and the exported `AddinCard` / `AddinKv`. The manifest stays `planned` with no path, as TPL-23 (gallery only).

Deviations: the reviewer's ring and the preparer's signed chip are drawn in the pane (C-25's `SignOffSlots` carries actor and checks a workbook pane does not have); the Word page shows only the two lines the seed holds (the two incoming changes' "before" values), the first on the amber tint; the copy keys live in the specimen's `copy.ts`.
