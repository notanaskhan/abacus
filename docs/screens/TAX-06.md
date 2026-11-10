# TAX-06 · Return › Issues (Feld 2025 Form 1040)

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | T9 preset issues-individual (546 = 262 + ≈260 · 433 · 377) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-06 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P0 |
| Manifest status | planned |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Default (18A selected; three-way lighting) | planned |
| b | Action required (Draft K-1, Samuel, What it blocks, Mark as Resolved disabled "Resolves when the final K-1 is released") | planned |
| c | Waiting on client (estimates; "Requested Sep 1 · Claire Feld is uploading 2 files now") | planned |
| d | Review point (NYC residency; "Open residency workpaper") | planned |
| e | Agent fixing (spinner, Pill "In progress", run row) | planned |
| f | Resolved filter (3 rows, Aug 27–28) | planned |
| g | Empty ("No open issues.") | planned |
| loading | skeleton per the handoff | planned |
| not allowed | walled or out of scope: 404 (INV-3) | planned |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| Opens TXP-10 · Ridgeline 2025 Form 1065 issues | TXP-10 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
Counts 4 open = 2 + 1 + 1; 3 resolved; 7 raised Aug 25. "Open Ridgeline 1065" → TXP-10 (T-05; disabled with reason until T-05 flips). "Issue" ≠ to-do (SHL-17). DF-13: no propose-only checkbox

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
