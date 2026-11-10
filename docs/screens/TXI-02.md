# TXI-02 · K-1 treatment resolver · Ridgeline K-1 on the Feld 2025 Form 1040

| Field | Value |
|---|---|
| Route and params | per T-04 §5.1 (`/tax-returns/$returnId/…`) |
| Template and host frame | T3 two-pane variant: treatments flex 876 · viewer 490 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXI-02 …/` |
| Epic and tasks | T-04 · T-04-T02 (contract), T-04-T07 (fixtures), screen rows per §9 |
| Priority | P1 |
| Manifest status | planned |

## States
| Artboard | Data condition that produces it | Status |
|---|---|---|
| a | Proposed (7 awaiting one approval; treatment 8 Approved · SI 9:31) | planned |
| b | Approved (10:24 AM; collapses to checkpoint "K-1 treatments") | planned |
| c | Changed vs 2024 focus (PTET; note to confirm Colorado nonresident filing) | planned |
| d | Override (Passive · Nonpassive + required reason → "Overridden · SI") | planned |
| e | Released (Sep 15; Item L 1,914,050; basis 4,676,125) | planned |
| loading | skeleton per the handoff | planned |
| not allowed | walled or out of scope: 404 (INV-3) | planned |

## API
RW-1 and WS-1 (T-04-T05); matrix actions from `permission-matrix/tax.yaml` (T-04-T03).

## Links
Designed links from the handoff (`handoff-links.json`); the screen is planned, so none is wired yet.

| From | To | Status |
|---|---|---|
| Opens TAX-05 · Schedule E K-1 matrix | TAX-05 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TXP-12 · Ridgeline K-1 package | TXP-12 | planned (handoff link; T-04-T08 onward wires it) |
| Opens TXI-03 · state residency and allocation | TXI-03 | planned (handoff link; T-04-T08 onward wires it) |
| Opens SHL-08 with the cited region lit | SHL-08 | planned (handoff link; T-04-T08 onward wires it) |

## Notes
Mixed statuses inside one activity. Released state changing an approved treatment follows DEC-84 (re-proposal + issue; open question Q4). Resolver is generic per K-1 activity (Shah 1040 also receives a Ridgeline K-1)

## Acceptance
SPEC-649's criteria for this screen (T-04 §3); each becomes a test named "<ID> acceptance: <criterion>".
