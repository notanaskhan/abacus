# TAX-04 · Return › Review — Prepare preset (Feld 2025 Form 1040)

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | T3 Prepare preset (tree 214 · viewer 571 · sheets 571) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-04 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P0 |
| Manifest status | planned |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Unapproved (Review 36; lighting 1a→3b, 1b→3a; poster at 3600 ms) | planned |
| b | Approved ("✓ 1" in ink, Review 36→35, footer "× Unapprove Document", toast "Approved Halvard Securities 2025 Consolidated 1099") | planned |
| c | Mismatch (3b $14,280 vs 14,820, Approve disabled "Resolve 1 mismatch to approve", "Issue…") | planned |
| d | K-1 selected (DRAFT watermark, box 5 4,600 lit, 18A not lit, 2a keeps ⚑) | planned |
| e | Loading pages | planned |
| loading | skeleton per the handoff | planned |
| not allowed | walled or out of scope: 404 (INV-3) | planned |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| Box 18A is not on the worksheet · open issue in TAX-06 | TAX-06 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
Aug 26 snapshot (36 documents, 7 issues). Purple only through MatchProvider; typed form values `#6A98E8` only inside rendered forms. The Rhinebeck address on the 1099 is real seed data (drives the NYC review point). "2-Year Comparison" SheetTab hidden until T-08 (T08). README deviation: spec names C-08 but the canvas draws inline; build on the C-08 kit

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
