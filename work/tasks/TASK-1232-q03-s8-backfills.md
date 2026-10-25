---
id: TASK-1232
title: S8 back-fill suites for scope kinds, connections and ledger import, GL detail and roll-forward, classification and ledger formats (Q-03-T021, T022, T023, T024)
spec: SPEC-034
acceptance_criteria: [AC-2, AC-3, AC-4, AC-5, AC-7, AC-8, AC-9]
risk_zone: red
status: done
epic: Q-03
plan_key: Q-03-T021; Q-03-T022; Q-03-T023; Q-03-T024
branch: s8b-accept-tests
test_author: ayushkbhatia
test_session: 2026-10-25, branch s8b-accept-tests (one clean session per suite, following .claude/skills/ac-test-author/SKILL.md)
created: 2026-10-25
updated: 2026-10-25
---

## Objective
- **T021:** "Every scope kind has an allow, a deny and a cross-tenant case, and visible() agrees with authorise() in the property test."
- **T022:** "Connections stay read-only (CONN-001) in every test and a revoked connection makes no further call."
- **T023:** "A GL snapshot is never updated in place and a roll-forward copies no evidence version across work items."
- **T024:** "Each of the five ledger formats has a round-trip test and fulfilment never marks a request received without a human decision."

## Plan (red zone)
- **Files:** `backend/tests/integration/backfill/test_q03t021_scope_kinds.py`, `test_q03t022_connections_and_ledger_import.py`, `test_gl_detail.py`, `test_roll_forward.py`, `test_ledger_formats.py`, `test_classification_board.py`, helper `ledger_support.py`; `apps/web/src/legacy/q03ledgerstates.test.tsx`. `test_firm_level_reads.py` (TASK-029) re-run unchanged.
- **Production (small, local, three fixes):** `requests/lifecycle.py` `update_item` with `requests/service.py` `reclassify_described`; `evidence/board_summary.py`; `apps/web/src/legacy/GlExport.tsx`.
- **Rollback:** revert the commit.

## Results
- **T021 (36 pass; TASK-029's suite re-run, passes):** engagement, work_item, client, client_entity and portal_scope each with allow, deny and cross-tenant cases through `identity.api` (`visible_scope`, `authorise`) on the real tables; a walled person sees nothing of the client through any kind; `visible()` agrees with `authorise()` for every persona against every row, per kind (exhaustive parametrised, in the back-fill folder).
- **T022 (58 pass):** a spy wraps every connector in `connections.api.CONNECTORS` in every test: no write-shaped method and every call a contract read (CONN-001); after a revoke the connector is never called again. SPEC-020 AC-2 to AC-6 and Q3; SPEC-028 AC-1 to AC-6, AC-8, Q4 and the flag (AC-4 end to end: method `imported`, snapshot totals, item fulfilled; AC-6 wrong period for QuickBooks Online and Xero).
- **T023:** SPEC-034 AC-2 to AC-5, AC-7, AC-8 (app UPDATE and DELETE refused on the three GL tables, the trigger refuses even the owner, no entry joins a committed snapshot); SPEC-025 AC-2 roll-forward (11 pass: the proposal, confirm creates exactly what was confirmed, `engagement.rolled_forward`, **no evidence version copied**, walled 409 `team_member_unavailable`, manager 403).
- **T024:** five trial-balance and five GL formats each round-trip to literal balances; fulfilment is method `imported` and lands `uploaded`, never `received` (DEC-09); SPEC-022 AC-1 to AC-5; SPEC-034 AC-9 screen states (vitest, 7).

## Escaped defects (fixed; ED numbers to be assigned at merge: only ED-053 and ED-054 were reserved and TASK-1229 and TASK-1230 hold them)
Rows ready for `docs/quality/escaped-defects.md`:
- `| ED-0?? | 2026-10-25 | S8 | amber | requests/lifecycle.py update_item | TASK-038 | Q-03-T024 | SEV4 | integration | fixed | a changed description was never classified again, so the item kept its old tier or stayed unclassified (SPEC-022 §12, AC-1); now reclassified unless overridden or set by the methodology; test_ac1_a_changed_description_is_reclassified |`
- `| ED-0?? | 2026-10-25 | S8 | amber | evidence/board_summary.py | TASK-038 | Q-03-T024 | SEV4 | integration | fixed | the retrievable share divided A to C by classified items only (2 of 3), not by the request list (2 of 5) (SPEC-022 §4 "the retrievable share of the request list", AC-5); test_ac5_the_retrievable_share_is_of_the_whole_request_list |`
- `| ED-0?? | 2026-10-25 | S8 | amber | apps/web/src/legacy/GlExport.tsx | TASK-070 | Q-03-T024 | SEV4 | component | fixed | when the latest GL import could not be read the section said nothing, so a client could not tell an earlier upload from none (SPEC-034 AC-9); test_ac9_gl_error_state_is_said_in_words in legacy/q03ledgerstates.test.tsx |`

## Spec drift (followed the later decision)
- TASK-036 D1: completing a connection is `POST /v1/connections/complete`, not SPEC-020 §8's unauthenticated callback. D3 to D5 (fresh MFA to connect, `connection.check`, who hears of a revoke) and SPEC-028 Q4 (partner, manager and senior may upload for the client).
- TASK-052 and TASK-053: the import routes are `…/connection/import` and take no period, not §8's `/ledger-import?period_…`; format ids (`qbo_tb_csv`, `xero_tb_xlsx`) are looked up by system name from the formats route.

## Spec gaps (tests accept either answer)
- SPEC-020: whether a mismatched state burns the real user's state is unsaid; a client admin of another engagement in the same firm may get 403 or 404. AC-7 (connector conformance) stays with the unit suite.
- SPEC-028 §6: a trial-balance import snapshots only through the retrieval for an open tier A item; with none it is `received` with no snapshot, so the tests create the item first.
- A roll-forward proposal for another firm's entity answers 200 with an empty proposal, identical to an unknown entity (nothing leaks); asserted as such rather than 404.
- SPEC-034 AC-6 "same snapshot, same bytes" is not reachable over HTTP; untested. The Board's URL filters (SPEC-022 AC-5) stay with `Board.test.tsx`.

## Progress log
- 2026-10-25: four rows back-filled; three small defects fixed; `docs/quality/backfill.md` rows 029, 036, 038, 048, 052, 068, 069, 070 and 071 updated.
