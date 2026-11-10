# TXI-01 · Worksheet editor · Feld 2025 Form 1040 · New York IT-201

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | T3 variant, three panes: tree 300 · fields 566 · viewer 490 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXI-01 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P0 |
| Manifest status | fixture (T-04-T22: `screens/TXI-01`) |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Default (IT-201; line 20 lit against K-1 p.3 Box 18A) | planned |
| b | Provenance popover (SHL-09: 0 → 1,550, Samuel, checkpoint "K-1 box 18A") | planned |
| c | W-2 worksheet (Mercer Hill Health boxes 1–19, ✓ KO · ✓ OB, box 1 lit) | planned |
| d | Flagged (⚑ SI on NYC resident → TAX-06 review point) | planned |
| e | Agent-created field (IT-653 green +, "New this year — Ridgeline elected New York PTET for 2025") | planned |
| f | Signed-off section ("Signed off · SI 9:52 AM") | planned |
| g | Unresolved residency (NYC rows amber "Recomputed by CCH Axcess after import"; IT-360.1 added) | planned |
| loading | skeleton per the handoff | planned |
| not allowed | walled or out of scope: 404 (INV-3) | planned |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| ⓘ on line 20 opens SHL-09: updated at 9:31 AM from 0 by Samuel Ito | SHL-09 | planned (handoff link; T-04-T08 onward wires it) |
| ⚑ SI on New York City resident opens TAX-06 with the residency review point | TAX-06 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
No revision; spec wins over blueprint §5.8 (no 2441). Line 47a provenance in the spec shows rate-schedule arithmetic: per DEC-77 it is relabelled as an engine import (T08). TSJ: W-2 items S, K-1 items T, joint J (built screenshot omits J on Filing status — use the spec). Both provenance cases (line 20, and J06 8b Halvard 2,190 → 2,310 on the federal interest worksheet) must work

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
