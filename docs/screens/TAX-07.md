# TAX-07 · Return › Activity & Checkpoints (Feld 2025 Form 1040)

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | T2 single-pane variant (activity 1006 + checkpoints 360) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TAX-07 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P0 |
| Manifest status | planned |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Default (24 events; Manager review checkpoint Current + starred) | planned |
| b | Proposed checkpoint ("☰ 1 proposed", "K-1 box 18A · Proposed · Review") | planned |
| b2 | Reviewing the proposal (SHL-16 diff with agent steps) | planned |
| c | No changes needed (9:31 AM; Issues 4→3; out of sync until export) | planned |
| d | Delivered (Sep 19; accepted IRS + NY; Partner approval current) | planned |
| e | Filtered "Agent" | planned |
| e2 | Empty filter ("No events match this filter.") | planned |
| f | Checkpoint diff (Initial draft; Return Drafter steps; Restore…; Compare) | planned |
| loading | skeleton per the handoff | planned |
| not allowed | walled or out of scope: 404 (INV-3) | planned |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| Opens INB-01 · Claire Feld’s email, 2 attachments waiting | INB-01 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TAX-09 · import history · 2025I:FeldJ:V3 | TAX-09 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TAX-05 · 1040 Review Checklist v6, L1 sign-off | TAX-05 | planned (handoff link; T-04-T08 onward wires it) |
| Opens SHL-08 · Claire_Feld_2025_Residency_Answers.pdf | SHL-08 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TAX-06 · resolved issue “Refund bank account required” | TAX-06 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TXP-12 · Ridgeline K-1 package, draft K-1 | TXP-12 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TAX-12 · Form 4868 and IT-370 acknowledgements | TAX-12 | planned (handoff link; T-04-T08 onward wires it) |
| Opens BND-01 · Feld 2025 Binder, 7 requests | BND-01 | planned (handoff link; T-04-T08 onward wires it) |
| Opens SIG-01 · TY2025 engagement letter envelope | SIG-01 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
f, b2, e2 were added during the build (README). Engine ids V1 Feb 3 → V2 Apr 14 → V3 Sep 10. "Amend…" (TAX-16) is not drawn and stays out (DF-08, T-08). Markers only `#2B1F17` and ink-3; no avatars

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
