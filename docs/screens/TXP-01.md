# TXP-01 · Review › Summary (preparer memo) · Ridgeline

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/summary` |
| Template and host frame | T10 document on well, structure 470 + paper pane 896 (868 card) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-01 Review - Summary - Ridgeline preparer memo/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Samuel Ito (Tax Manager, reviewer) |
| Flags | `tax.entity_workspace`; drafting and Regenerate sections also `tax.entity_agents` |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | Adopted · awaiting the reviewer | Memo drafted by the agent and adopted by Olivia Sep 10 (L1); no L2 yet | Mon Sep 14, 2026, 9:24 AM CT | Sep 14 9:24 | D (blocking) · C report-only | planned |
| a2 | Citation · SHL-07 | Marker 2 hovered: Partners and Allocation rows and 331,405 lit purple across panes (360 ms) | Mon Sep 14, 2026, 9:24 AM CT | Sep 14 9:24 | D (blocking) · C report-only | planned |
| a3 | Sign-off · SHL-12 | SHL-12 open at L2 for Samuel | Mon Sep 14, 2026, 9:24 AM CT | Sep 14 9:24 | D (blocking) · C report-only | planned |
| b | Drafting | Memo run active; sections stream as skeletons | Mon Sep 14, 2026, 9:24 AM CT | memo run active | D (blocking) · C report-only | planned |
| c | Approved | L2 recorded "Approved by Samuel Ito · Sep 14, 9:40 AM", rail "✓ SI" | Mon Sep 14, 2026, 9:40 AM CT | after L2 | D (blocking) · C report-only | planned |
| d | Stale | After the 9:51 fix the figure fingerprint differs: "ending capital 6,860,000 → 6,866,200"; Regenerate sections | Mon Sep 14, 2026, 9:52 AM CT | after the M-2 fix | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-01 a, a2, a3, b, c, d` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/memo`
- `POST /v1/tax-returns/{id}/memo/draft`
- `PATCH /v1/tax-returns/{id}/memo/sections/{key}`
- `POST /v1/tax-returns/{id}/memo/adopt`
- `POST /v1/sign-offs (target preparer_memo, L2)`
- `GET /v1/tax-returns/{id}/opportunities`
- `GET /v1/tax-returns/{id}/general-information`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Citation marker | SHL-07 then SHL-08 | planned |
| Approve… | SHL-12 (L2) | planned |
| Raise with client… | TAX-15 (T-08) / PRJ-01 (T-09) | planned |

## Notes

The paper card fills the pane (spec over the catalogue's 600 px). Memo status words join the registry (T-05-T05). "Accrual" appears only as an accounting-method value. Bridge: 3,776,500 + 96,400 − 2,641,300 = 1,231,600; + 18,400 + 6,200 = 1,256,200; − 6,200 = 1,250,000.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-01 acceptance: <criterion>".
