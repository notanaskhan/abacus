# TXP-10 · Return › Issues · Ridgeline 2025 Form 1065

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/issues` (`?issue=` selects; `?step=` filters by run step) |
| Template and host frame | T9 `issues-entity` preset (queue 470 · detail flex), from TPL-09 frame C |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXP-10 Return - Issues - Ridgeline 2025 Form 1065/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-05 · SPEC-651 · T-05-T01 (contract), T-05-T03 (undesigned states), T-05-T06 (stubs), screen rows per T-05 §9 |
| Persona | Samuel Ito (Tax Manager, reviewer) |
| Flags | `tax.entity_workspace` |
| Priority | P0 |
| Manifest status | planned |

## States

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | Review point | M-2 review point selected: proposed-fix ApprovalCard with both changes and the evidence | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| a2 | Approve fix | SHL-10 over a with a matching `seen_hash` | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| b | Waiting on the client | §754 issue, Waiting on the client, assigned to Owen Calder; POR-04 request preview in template wording; Send reminder | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| c | Agent fixing | Fix approved at 9:51: issue In progress, agent monogram spinner, mini run row (Run 3) | Mon Sep 14, 2026, 9:51 AM CT | Run 3 running | D (blocking) · C report-only | planned |
| d | Resolved | "Resolved by Samuel Ito · 9:52 AM", badge Issues 10 | Mon Sep 14, 2026, 9:52 AM CT | after the fix | D (blocking) · C report-only | planned |
| e | No issue selected | Queue with no selection | Mon Sep 14, 2026, 9:24 AM CT | Run 2 | D (blocking) · C report-only | planned |
| f | No open issues | Queue empty; Show resolved lists 11 | Mon Sep 14, 2026, 9:24 AM CT | all resolved | D (blocking) · C report-only | planned |
| loading | — | skeleton per the handoff (the screen's Building state where it has one) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | designed in T-05-T03 (never blank) | — | — | — | planned |

Fixture scenario set: `TXP-10 a, a2, b, c, d, e, f` (T-05 §5.3), derived from the golden figures, never typed by hand.

## API

Every artboard reads this endpoint set (T-05 §4.3; stubs in T-05-T06, `docs/contracts/tax-workbook.md`):

- `GET /v1/tax-returns/{id}/issues?section=&status=&step=&q=&show_resolved=`
- `P-04 issue routes (assign, resolve, send to client)`
- `POST /v1/proposals/{id}/approve | reject (seen_hash)`
- `POST /v1/proposals/{id}/undo`

Matrix actions from `permission-matrix/tax.yaml` (T-05-T04): every human verb `agent: deny`.

## Links

| From | To | Status |
|---|---|---|
| Approve fix | SHL-10 | planned |
| Linked cells | TXP-11 split (match lighting) | planned |
| Send to client… | SHL-15 → POR-04 request | planned |
| Fix instructions | SHL-15 (`issues.fix_runner`, T-04) | planned |

## Notes

Counts 5 + 6 = 11 equal the badge and TXP-00's open items; the badge is derived, never stored. *Why this was surfaced* uses the olive check disc, never sparkles. Issues are C3's cross-module primitive (P-04), never a TXP table.

DF-34: Schedule L follows pack 08 (1200 → L5, mortgage → L18, 2000 split from 2050); open issues read 11 and decrement to 10 here (T-05) and 9 with T-06; the canonical name is "Ridgeline Property Partners, LP".

## Deviations

- Import-mode steps (`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`) read the firm's report or keyed cells until T-06 (SPEC-651 §2.2).
- Schedule K and capital are read models over workbook cells; no `schedule_k_lines` or `capital_account_lines` tables (T-05 OQ-8).
- TXP-12 (K-1 package) is T-02's screen; T-05 only links to it.

### Designed states the handoff lacks (T-05-T03)

| State | What renders | None blank |
|---|---|---|
| Agent off | No agent-raised issues appear new; existing issues stay; "Set Fix Instructions" is disabled with the capability reason; every resolution is a person's. | yes |
| Flag off (`tax.entity_workspace`) | The 1065 opens TAX-02's coordination view as today (F13); no entity route answers and no pane renders blank. Not a screen state: the screen is unreachable. | yes |
| Consent blocked (§7216) | Fix runner disabled with "§7216 AI consent — Ridgeline (1 of 2 signed)"; issues list as drawn. | yes |
| Import mode | Issues from an import-mode step name the import as their source. | yes |
| Entitlement refused (`tax.entity_returns`, CPA memos unsigned, non-synthetic firm) | The return opens the coordination view with the designed locked card: title "Entity return workspace", body "Opens once the firm's entity returns are set up." (undesigned, T-05-T03), no workbook route answers (F13). | yes |

Every string above with no handoff source is undesigned (T-05-T03) and is replaced by the handoff's copy when one lands; the consent line is the spec's (SPEC-651 F13).

## Acceptance

SPEC-651's criteria for this screen; each becomes a test named "TXP-10 acceptance: <criterion>".
