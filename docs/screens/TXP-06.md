# TXP-06 · Allocation Structure (modal sheet) · Ridgeline and Harborview

| Field | Value |
|---|---|
| Route and params | `?ov=allocation` over `/tax-returns/$returnId/review/schedule-k` |
| Template and host frame | O4 full modal sheet over TXP-05 |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-06 Allocation Structure -modal sheet- - Ridgeline and Harborview 20/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Samuel Ito (Tax Manager, reviewer) |
| Flags | `tax.entity_workspace`; agreement reader `tax.entity_agents` |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | Ridgeline · approved | Ridgeline straight percentage, §706(d) interim closing (monthly) approved at L3 | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| a2 | Partner series | Meera Shah picked in the rail: her series outlined in every bar; tooltip "Meera Shah · 238,678 · 38% of 628,100" | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| b | Harborview · targeted waterfall | Harborview Dental Properties targeted waterfall, approved Aug 28 | Mon Sep 14, 2026, 9:24 AM CT | Harborview | D (blocking) · C report-only | planned |
| c | Pending approval | Ridgeline proposed by the agreement reader with two clause citations (Sep 8), Pending approval | Mon Sep 14, 2026, 9:24 AM CT | Sep 8 snapshot | D (blocking) · C report-only | planned |
| c2 | Sign off | SHL-12 at Manager L3 over c | Mon Sep 14, 2026, 9:24 AM CT | Sep 8 snapshot | D (blocking) · C report-only | planned |
| d | Editing a rung | Harborview rung edited inline (pref 8%, catch-up 20%, promote 20/80): preview recomputes, back-solve Pending until Save | Mon Sep 14, 2026, 9:24 AM CT | Harborview | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-06 a, a2, b, c, c2, d` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/allocation-structure`
- `PUT /v1/tax-returns/{id}/allocation-structure/draft`
- `POST /v1/tax-returns/{id}/allocation-structure/preview`
- `POST /v1/sign-offs (target allocation_structure, L3, seen_hash)`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Clause citation | SHL-07 then SHL-08 (LPA §4.1, Assignment §3) | planned |
| Approve structure | SHL-12 (Manager L3) | planned |
| Esc / X | TXP-05 (focus returns to the trigger) | planned |

## Notes

Approval is an SHL-12 L3 sign-off, not SHL-10. Ridgeline: two periods of 628,100, partner totals 1,256,200, Meera Shah "238,678 · 38% of 628,100". Harborview: 4,000,000 + 312,000 + 78,000 + 510,000 = 4,900,000, back-solve plugs 900,000, GP 20%. The fifth partner fill uses `--surface`.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- The "Edit rules" link visible in the built screenshot TXP-06b is not in the spec and is not built.
- The handoff names Meera Shah as the viewer of a2; the persona is Samuel Ito and Meera Shah is the outlined series.
- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-06 acceptance: <criterion>".
