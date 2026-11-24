# TPL-21 · T19 Board specimen · Granite Peak FY2026 audit programs · Sep 24

| Field | Value |
|---|---|
| Route and params | none (gallery `/components/screens/TPL-21`); artboards `/components/screens/TPL-21?st=…` |
| Template and host frame | T19 record (navigator 280 + 4 × 262) |
| Surface | firm (gallery `/components` only until a consumer epic imports the kit) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-21 T19 Board specimen - Granite Peak FY2026 audit programs - Sep 24/` |
| Epic and tasks | F-08 · F-08 epic (no SPEC: gallery-only kits); F-08-T01 (TASK-8616); kit and specimen tasks per `docs/plan/epics/F-08.tasks.csv` |
| Manifest status | planned |

Parity tier target: B (F-08 §5.5). Copy keys live in `apps/web/src/screens/TPL-21/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | Default | `tpl21-sep24` | Cole Hart | Thu Sep 24, 9:30 AM | planned | AY |
| b | Dragging | `tpl21-sep24` | Cole Hart | Mon Sep 14, 2026, 10:05 AM | planned | AY |
| c | Dropped | `tpl21-sep24` | Cole Hart | Mon Sep 14, 2026, 10:05 AM | planned | AY |
| d | Drop guard | `tpl21-sep24` | Hannah Leclerc | Mon Sep 14, 2026, 9:42 AM | planned | AY |
| e | Binder view | `tpl21-sep24` | Cole Hart | Thursday 24 September 2026, 9:30 AM CT | planned | AY |
| f | Overlay states | `tpl21-sep24` | Cole Hart | Thursday 24 September 2026, 9:30 AM CT | planned | AY |

## Deviations
- Kit-file conflict resolved here: TPL-21f = overlay states; control = T19h; close = T19l.
- Columns 4 · 5 · 2 · 2 then 3 · 6 · 2 · 2 after the BH-FS-430 move; binder Preparer 12 of 21 · Reviewer 10 of 21.
- Persona Cole Hart; Hannah Leclerc on d; ?as=simone-baptiste resolves to a fixture session (F-08-T02).

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| tooltip or toast inside kits/Board Specimen | SHL-12 | designed (handoff link graph) |
| tooltip or toast inside kits/Board Specimen | TPL-20 | designed (handoff link graph) |
| tooltip or toast inside kits/Board Specimen | AUD-04 | designed (handoff link graph) |
| tooltip or toast inside kits/Board Specimen | ENG-11 | designed (handoff link graph) |
| tooltip or toast inside kits/Board Specimen | ENG-01 | designed (handoff link graph) |
| tooltip or toast inside kits/Board Specimen | AUD-02 | designed (handoff link graph) |
| tooltip or toast inside kits/Board Specimen | AUD-36 | designed (handoff link graph) |

## Built (F-08-T23, DEC-5931)

Gallery specimen at `/components/screens/TPL-21?st=a…f` (`apps/web/src/gallery/specimens/TPL-21`) on T19 `BoardLayout` with the Granite Peak audit-program seed (`fixtures/seed/granite-peak-fy2026-board.ts`, now with each program's audit area, C-26 state and the area lanes; footed in `granite-peak-fy2026.foot.test.ts`). Headers 4 · 5 · 2 · 2 at 9:30 AM, 3 · 6 · 2 · 2 after the 10:05 AM drop; BH-FS-430 Agent running 40%; Binder footer "Preparer 12 of 21 · Reviewer 10 of 21"; f is the overlay strip (specimen, not seed). The manifest stays `planned` (gallery only).

Deviations: the record subbar and tabs bar are drawn as text rows (the shell's RecordHeader belongs to ENG-10 in K-04); the lane's right summary ("1 in review") and Presence are not drawn; the SHL-13 dock in c is a static card (the dock itself is P-04's).
