# TXP-05 · Review › Schedule K · Ridgeline 2025 Form 1065

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/schedule-k` (`?view=federal|state`) |
| Template and host frame | T6 workbook layout |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-05 Review - Schedule K - Ridgeline 2025 Form 1065/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Samuel Ito (Tax Manager, reviewer) |
| Flags | `tax.entity_workspace` |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | Federal · as drafted | Approved structure; K = Σ K-1 per line; Item L off 6,200 while the M-2 issue is open | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only, **lock proposed** | planned |
| a2 | Line 2 · Form 8825 | Form 8825 popover: the three properties behind 1,231,600 | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| a3 | Cell provenance | SHL-09: `06 Schedule K!C31` after TJE-1 | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| a4 | Item L off 6,200 | Item L popover routing to TXP-07 and TXP-10 | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| a5 | Partner header | Partner header menu: the recipient's K-1 package (TXP-12), TAX-11 planned | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| b | State K-1 amounts | `view=state`: IL, CO and NY figures from sheet 08 (imported or keyed in T-05) | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| c | After the M-2 fix | Item L ties at 6,866,200 | Mon Sep 14, 2026, 9:52 AM CT | after the fix | D (blocking) · C report-only | planned |
| d | Building | Run active on the K-1 steps: skeleton rows | Mon Sep 14, 2026, 9:24 AM CT | run active | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-05 a, a2–a5, b, c, d` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/schedules/k?view=federal|state`
- `GET /v1/tax-returns/{id}/schedules/k/lines/{line}/breakdown`
- `GET /v1/tax-returns/{id}/workbook/cells/{address}`
- `GET /v1/tax-returns/{id}/allocation-structure`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Allocation Structure… | TXP-06 (`?ov=allocation`) | planned |
| Item L off 6,200 | TXP-07 and TXP-10 | planned |
| Partner header | TXP-12 (T-02); TAX-11 K-1 page (T-06) | planned |
| Form preview | TAX-11 (T-06) | planned |

## Notes

K = Σ of five K-1s: line 2 1,231,600 · interest 18,400 · 18a 6,200 · 19a 600,000 · Item K 11,048,300; Pell Street Ventures box 2 400,270 = 35% × 615,800 + 30% × 615,800. No guaranteed payments or SE income for this rental partnership; §199A 20c renders "stmt".

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

### Designed states the handoff lacks (T-05-T03)

| State | What renders | None blank |
|---|---|---|
| Agent off | No agent notes on lines; every line's provenance is code or a person's edit; the screen is otherwise as drawn. | yes |
| Flag off (`tax.entity_workspace`) | The 1065 opens TAX-02's coordination view as today (F13); no entity route answers and no pane renders blank. Not a screen state: the screen is unreachable. | yes |
| Consent blocked (§7216) | Same as agent off for model notes, with "§7216 AI consent — Ridgeline (1 of 2 signed)" in the header's info chip; figures are code's. | yes |
| Import mode | Lines fed by `state_k1s_k3s` or `apportionment_ptet` show the import chip and cannot be edited here until T-06. | yes |
| Entitlement refused (`tax.entity_returns`, CPA memos unsigned, non-synthetic firm) | The return opens the coordination view with the designed locked card: title "Entity return workspace", body "Opens once the firm's entity returns are set up." (undesigned, T-05-T03), no workbook route answers (F13). | yes |

Every string above with no handoff source is undesigned (T-05-T03) and is replaced by the handoff's copy when one lands; the consent line is the spec's (SPEC-651 F13).

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-05 acceptance: <criterion>".
