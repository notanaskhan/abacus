# TXP-00 · Return › Agent (entity returns) · Ridgeline Property Partners, LP · 2025 Form 1065

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId` (1065 by form-family dispatch; 1040 and 1041 stay on TAX-02) |
| Template and host frame | T2 record cockpit, rail 330 + canvas flex, no dock |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-00 Return - Agent - entity returns/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Olivia Brandt (Tax Senior, preparer) |
| Flags | `tax.entity_workspace` (screen), `tax.workbook_run` (▶ Run, re-runs) |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | Complete with open items | Run 2 · Sep 10, 3:31 → 4:12 PM · 10 of 10 · 11 open items (1 + 1 + 2 + 4 + 1 + 2); each count links to TXP-10 filtered to the step | Mon Sep 14, 2026, 9:24 AM CT | Run 2 snapshot | D (blocking) · C report-only | planned |
| b | Running · Run 3 | Run 3 after the 9:51 M-2 fix: 7 of 10, three rows running, live dot, bottom running pill (ScriptedRunSource frozen mid-run under `?static=1`) | Mon Sep 14, 2026, 9:52 AM CT | Run 3 running | D (blocking) · C report-only | planned |
| c | Idle · Jun 2 | No run started; every row an empty ring "Not started"; primary ▶ Run | Tue Jun 2, 2026 | before Run 1 | D (blocking) · C report-only | planned |
| d | Needs input · Run 1, Sep 8 | Run 1 waiting on the §706(d) convention question (amber dot "Waiting on 1 answer"; options from Reg. §1.706-4; recommended Monthly cites Assignment §3) | Tue Sep 8, 2026, 10:02 AM CT | Run 1 snapshot | D (blocking) · C report-only | planned |
| e | Failed task | Run 1 stopped at Import trial balance: QBO connection health `needs_attention` (class `connection_needs_attention`); Retry · Reconnect · View run | Tue Sep 8, 2026, 10:02 AM CT | Run 1 snapshot | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-00 a, b, c, d, e` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/general-information`
- `GET /v1/tax-returns/{id}/workbook-runs`
- `POST /v1/tax-returns/{id}/workbook-runs`
- `GET /v1/agent-runs/{run}`
- `GET /v1/agent-runs/{run}/events (SSE; polling fallback)`
- `POST /v1/agent-runs/{run}/questions/{q}/answer | skip`
- `POST /v1/agent-runs/{run}/steps/{s}/retry`
- `GET /v1/tax-returns/{id}/issues (counts per step)`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Open-item count on a task row | TXP-10 `?step=<key>` | planned |
| View work | TXP-11 at the step's sheet | planned |
| View run | WB-09 | planned |
| Reconnect | A-02 connection panel (WB-11 when W-01 lands) | planned |
| Composer | TAX-08 (T-04) | planned |
| Links rail | CLI-02, ENG-02, BND-02, FIL-01 | planned |

## Notes

The spec's default is **a** (the catalogue's running card as main state loses). Six task groups, ten tasks (§2.2). The meta "27 accounts" (QBO) versus TXP-02's 28 rows (tax-only 4510-T) is explained in the meta line. The Agent tab has no Group B.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-00 acceptance: <criterion>".
