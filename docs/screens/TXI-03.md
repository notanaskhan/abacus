# TXI-03 · State residency & allocation · Feld 2025 Form 1040

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | T6 two-pane: residency 560 + allocation 806; control bar; tally strip |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXI-03 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P1 |
| Manifest status | planned |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Unresolved — Review point | planned |
| b | Confirmed ("Residency confirmed by Samuel Ito · Sep 15, 4:55 PM"; Issues 3→2) | planned |
| c | Action required (150 NYC days + Rhinebeck main home; option 2 Recommended; Ask the client primary) | planned |
| d | Ask the client (POR-04 preview, options Brooklyn / Rhinebeck / Both; only Samuel sends) | planned |
| e | Loading allocation ("Sourcing by property…") | planned |
| loading | skeleton per the handoff | planned |
| not allowed | walled or out of scope: 404 (INV-3) | planned |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| Opens POR-04 · the question to Claire Feld | POR-04 | planned (handoff link; T-04-T08 onward wires it) |
| Opens SHL-08 with the source lit | SHL-08 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TXI-01 · Form 1040 | TXI-01 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TXI-02 · treatment 6 · state sourcing | TXI-02 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
Confirm is an SHL-10 proposal (Q1). No "$" in tables. Open in Excel = deterministic xlsx. For real firms the question wording comes from a firm template, not model text (DEC-79)

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
