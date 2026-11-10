# TXP-07 · Review › Capital Accounts · Ridgeline 2025 Form 1065

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/capital` (`?view=by_partner|by_movement`) |
| Template and host frame | T6 workbook layout, grown from the TPL-06 specimen (F-06-T20) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-07 Review - Capital Accounts - Ridgeline 2025 Form 1065/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Samuel Ito (Tax Manager, reviewer) |
| Flags | `tax.entity_workspace` |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | By partner · as drafted | Tax column omits tax-exempt interest: "M-2 ties · off 6,200", five amber cells | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only, **lock proposed** | planned |
| a2 | Tax-exempt cell | Provenance on `05 Capital!H9` empty, expected `'06 Schedule K'!C31 × 38%` = 2,356 | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| a3 | Pell Street transfer | Transfer row: 331,405 moves at 6/30 in all three columns, Transfers nets to 0 | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| b | By movement | `view=by_movement` | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| b2 | Sign off · blocked | SHL-12 blocked "1 tie-out is off · resolve it or sign off with a note"; POST without a note → 409 `tie_out_off` | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| c | After the fix | Other increases 6,200, END TOTAL 6,866,200, tie passes; an earlier sign-off computes stale | Mon Sep 14, 2026, 9:52 AM CT | after the fix | D (blocking) · C report-only | planned |
| d | Computing | Capital steps running: tally values fade in 45 ms apart, rows 70 ms (captured at the final frame) | Mon Sep 14, 2026, 9:24 AM CT | run active | D (blocking) · C report-only | planned |
| e | Signed off | Section signed: header "Reviewed · SI", "✓ SI" | Mon Sep 14, 2026, 9:52 AM CT | after sign-off | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-07 a, a2, a3, b, b2, c, d, e` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/capital-accounts?view=by_partner|by_movement`
- `GET /v1/tax-returns/{id}/schedules/m2?variant=as_drafted|with_fix`
- `GET /v1/tax-returns/{id}/workbook/cells/{address}`
- `GET /v1/tax-returns/{id}/sections`
- `POST /v1/tax-returns/{id}/sections/capital-accounts/sign-off`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Amber cell | SHL-09 (expected value) | planned |
| M-2 ties · off 6,200 | TXP-10 (the M-2 review point) | planned |
| Sign off… | SHL-12 (blocked state while the tie is off) | planned |
| Allocation basis (tooltip) | TXP-06 (the Allocation Structure) | planned |

## Notes

Columns Tax · 704(b) · Book (tax basis); never a GAAP column (spec over catalogue). Staggered reveal (values 45 ms, rows 70 ms apart), none under reduced motion. Transfer 331,405 = 2,319,835 × 5/35 at 6/30 in all three columns.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

### Designed states the handoff lacks (T-05-T03)

| State | What renders | None blank |
|---|---|---|
| Agent off | No agent reconciliation notes; the roll-forward and the tie-out tally are code's and render as drawn. | yes |
| Flag off (`tax.entity_workspace`) | The 1065 opens TAX-02's coordination view as today (F13); no entity route answers and no pane renders blank. Not a screen state: the screen is unreachable. | yes |
| Consent blocked (§7216) | As agent off, with "§7216 AI consent — Ridgeline (1 of 2 signed)" in the info chip. | yes |
| Import mode | A capital line from an imported state K-1 shows the import chip. | yes |
| Entitlement refused (`tax.entity_returns`, CPA memos unsigned, non-synthetic firm) | The return opens the coordination view with the designed locked card: title "Entity return workspace", body "Opens once the firm's entity returns are set up." (undesigned, T-05-T03), no workbook route answers (F13). | yes |

Every string above with no handoff source is undesigned (T-05-T03) and is replaced by the handoff's copy when one lands; the consent line is the spec's (SPEC-651 F13).

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-07 acceptance: <criterion>".
