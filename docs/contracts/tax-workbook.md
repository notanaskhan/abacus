# Tax workbook · entity returns (v1)

| Field | Value |
|---|---|
| Version | v1 |
| Status | **frozen at v1** (T-05-T46, 2026-11-13, DEC-4712; snapshot `backend/tests/contracts/tax_workbook/v1.json`); live behind `tax.entity_workspace`; the routes §9 lists as later rows still answer 501 |
| Provider epic | T-05 (SPEC-651) |
| Consumers | TXP-00, TXP-01, TXP-02, TXP-05, TXP-06, TXP-07, TXP-10, TXP-11 (T-05 FE rows); T-07 (the workbook engine, run plan and K-1 draft payload), T-06 (TXP-03, 04, 08, 09 reuse the reads; E3, E4, E8–E12 on the same workbook), T-04 and T-02 (K-1 drafts into `k1_packages`); T-08 (TAX-10 two-year) |
| Flags | `tax.entity_workspace` (routes), `tax.workbook_run` (runs and imports), `tax.entity_agents` (model-backed steps); entitlement `tax_entity_returns` (requires review) |
| Code | `backend/src/abacus/modules/tax/workbook_contract.py` |
| Matrix | T-05-T04's rows in `docs/architecture/permission-matrix/tax.yaml` |

## 1. Who may call it
Every route answers, in order:
1. a client principal answers 404;
2. `tax.entity_workspace` off for the firm answers 404;
3. the route's one matrix action applies (walls first, 404);
4. then 501 until its build task.

The P-10 run API (`/v1/agent-runs/{run}` …), P-04's sign-off, proposal, issue and decision routes, and A-06's C8 entry routes are reused, not repeated here.

| Operation | Method and path | Action |
|---|---|---|
| Rail facts | `GET /v1/tax-returns/{id}/general-information` | `tax_return.read` |
| Partners, periods, transfers | `GET /v1/tax-returns/{id}/partners` | `tax_return.read` |
| Replace ownership (one version) | `PUT /v1/tax-returns/{id}/ownership` | `tax_ownership.edit` |
| Workbook sheets and versions | `GET /v1/tax-returns/{id}/workbook` | `workbook.read` |
| Cells of a sheet | `GET /v1/tax-returns/{id}/workbook/sheets/{sheet}?version=&range=` | `workbook.read` |
| Cell provenance | `GET /v1/tax-returns/{id}/workbook/cells/{address}?version=` | `workbook.read` |
| Edit a cell | `PUT /v1/tax-returns/{id}/workbook/cells/{address}` | `workbook.edit` |
| The workbook xlsx | `GET /v1/tax-returns/{id}/workbook/export.xlsx?version=&sheet=` | `workbook.export` (fresh MFA) |
| Import a report | `POST /v1/tax-returns/{id}/workbook/imports?kind=` | `workbook_import.create` |
| Start a run | `POST /v1/tax-returns/{id}/workbook-runs` → 202 `{run_id, run_no}` | `workbook_run.start` |
| Run history | `GET /v1/tax-returns/{id}/workbook-runs` | `workbook.read` |
| TB → TTB | `GET /v1/tax-returns/{id}/trial-balance?view=&statement=&filter=&version=` | `workbook.read` |
| Tallies | `GET /v1/tax-returns/{id}/trial-balance/tallies` | `workbook.read` |
| AJE, RJE, TJE | `GET /v1/tax-returns/{id}/journal-entries` | `adjusted_tb.read` (A-06) |
| Form line picker | `GET /v1/form-lines?form=&tax_year=&q=` | `reference_set.read` (K-02) |
| Pick a mapping | `POST /v1/tax-returns/{id}/mappings` | `workbook.edit`; maps only for `tax_mapping.approve` (DEC-4629) |
| Schedule K | `GET /v1/tax-returns/{id}/schedules/k?view=&version=` | `workbook.read` |
| Form 8825 by property | `GET /v1/tax-returns/{id}/schedules/k/lines/{line}/breakdown` | `workbook.read` |
| Capital accounts | `GET /v1/tax-returns/{id}/capital-accounts?view=&version=` | `workbook.read` |
| Schedule M-2 | `GET /v1/tax-returns/{id}/schedules/m2?variant=` | `workbook.read` |
| Allocation structure | `GET /v1/tax-returns/{id}/allocation-structure?version=` | `allocation_structure.read` |
| A new structure draft | `PUT /v1/tax-returns/{id}/allocation-structure/draft` | `allocation_structure.edit` |
| Preview without saving | `POST /v1/tax-returns/{id}/allocation-structure/preview` | `allocation_structure.read` |
| Approve the structure (L3) and re-run capital and K-1s | `POST /v1/tax-returns/{id}/allocation-structure/approve` (T-05-T41) | `sign_off.create` (P-04's L3 rules) |
| Sections and their tallies | `GET /v1/tax-returns/{id}/sections` | `workbook.read` |
| A section's sign-off | `POST /v1/tax-returns/{id}/sections/{key}/sign-off` | `sign_off.create` (P-04 levels) |
| TXP-10's issues | `GET /v1/tax-returns/{id}/issues?section=&status=&step=&q=&show_resolved=` | `issue.read` (P-04) |
| The preparer memo | `GET /v1/tax-returns/{id}/memo` | `tax_memo.read` |
| Ask for a memo draft | `POST /v1/tax-returns/{id}/memo/draft` → 202 | `tax_memo.draft` |
| Edit a memo section | `PATCH /v1/tax-returns/{id}/memo/sections/{key}` | `tax_memo.edit` |
| Adopt the memo (L1) | `POST /v1/tax-returns/{id}/memo/adopt` | `sign_off.create` (function_in preparer) |
| Opportunities | `GET /v1/tax-returns/{id}/opportunities` | `tax_memo.read` |
| Accrued vs the engine | `GET /v1/tax-returns/{id}/reconciliation?checkpoint=` | `tax_reconciliation.read` |

Served so far (S40): the trial balance, its tallies and journal entries (T-05-T33, DEC-4618); Schedule K, the Form 8825 breakdown, capital accounts and the M-2 (T-05-T34, DEC-4619). T-05-T34 adds, additively: `WorkbookCapitalRowOut.name`, `WorkbookCapitalAccountsOut.totals` and `.item_l`, `WorkbookM2Out.lines` and `.item_l` (Item L's ending capital against the M-2's line 9: `tie`, or `off` with the difference).

TXP-02's rest (T-05-T37, DEC-4629), all additive: `WorkbookTbRowOut.cells` (each amount's sheet 01 address by column, `utb` `aje` `rje` `atb`, for SHL-09); tallies `balance_sheet`, `capital_tie` and `retained_earnings` (the two M-2 checks read `pending` until sheet 07 is written); `terms` on tallies and figures (each derivation term with its label, amount and `+` or `-`); `WorkbookJournalEntryOut.description`, `.lines` and `.approval` (the O2 drawer). `GET /v1/form-lines` is served (the published set's mappable lines; 404 when none is published). `POST …/mappings` is served: the tax reviewer's pick maps the account (`state: mapped`, audited `tax.mapping_recorded`); anyone else's raises a review note proposing the line (`state: flagged`, `note_id`) and maps nothing. Proposals stay the agent's (ADR-161), so a person's pick is never one. `WorkbookMappingProposedOut` changed from `{proposal_id}` to `{state, account_code, form_line_key, note_id}`; the route was a 501 stub with no consumer.

TXP-11's rest (T-05-T38, DEC-4630), all additive: `WorkbookOut.versions` (the finished runs, newest first; `version` is the newest, the live workbook). `GET …/workbook/sheets/{sheet}?version=n` reads an earlier run's sheet as it stood when that run finished (404 for an unknown version). The live sheet fills each cell's `citation_ids` and its writer (`author`).

The cell edit (T-05-T35, DEC-4620) is served. The cell path names the sheet (`05!H12`, URL-encoded). The preparer's edit recomputes its dependents synchronously, up to 500 cells; beyond that it answers 422 `recompute_too_large`. It then saves a checkpoint named "Edited 05 Capital!H12 by ‹person›". A reviewer's edit becomes a review note anchored on the cell: the response has state `flagged` and carries `proposal_note_id`, and the cell does not change. A person with neither function gets 403 `preparer_function_required`. The other errors are 409 `cell_version_conflict` or `cells_locked_by_run`, and 422 `formula_invalid` for grammar errors and cycles. `WorkbookCellOut` gains `recomputed`, `proposal_note_id` and `checkpoint_id`, all additive.

T-05-T37 (DEC-4622) adds, additively, `WorkbookTbRowOut.adjusted`, `.prior_year` and `.group`; `WorkbookTrialBalanceOut.totals` (`WorkbookTbTotalOut` per section, then `tb_total`); and `WorkbookTalliesOut.figures` (`gross_rents`, `total_deductions`, `net_rental_income`, `book_total_assets`), all computed by the server.

## 2. Models and classification
Pydantic models in the code file, every field classified. Every workbook value, formula, memo body, K-1 or partner payload and figure is tax return information (Restricted, `tri`; C19). A partner's TIN is never in a response: `tin_last4` only; the reveal is P-12's logged path (`tin.reveal`, step-up MFA, `not_offshore`). Money is exact `Decimal` with two places.

## 3. Status words
From `docs/product/status-vocabulary.yaml` (T-05-T05):
- `preparer_memo`: Drafting, Adopted, Approved, Stale (derived).
- `allocation_structure`: Editing, Pending approval, Approved, Superseded.
- `tie_out_tally`: tie, off {amount}, Check, Pending, Ties once posted, Reconciled.
- `agent_run_step`, with TXP-00's context labels.
- `return`, with "Working" (`subbar_entity_returns`).

## 4. Human-only actions
Each is a person's own act (`agent: deny` in the matrix; the service's `require_live_human`; the database's human-only CHECKs where a decision row exists):
- `workbook.edit`: a cell edit (a reviewer's edit becomes a proposal);
- `workbook.export`: the xlsx;
- `workbook_import.create`: an import;
- `workbook_run.start`: starting or re-running a run (its steps run as that person via Agent);
- `tax_ownership.edit`: ownership periods and transfers, each with its clause citation;
- `allocation_structure.edit`: a structure draft;
- `tax_memo.draft`: asking for a memo draft (the run proposes, never adopts);
- `tax_memo.edit`: writing a memo section;
- the L1 adoption, the L2 memo approval and the L3 structure approval (P-04 sign-offs);
- a mapping's approval (P-04 `proposal.approve`, function_in tax reviewer);
- `decision.decide` on `section_754`;
- an issue's resolution (P-04, ISSUE-001).

## 5. Errors
409:
- `cell_version_conflict`, `cells_locked_by_run`, `run_in_progress`, `tie_out_off`, `proposal_changed`, `export_blocked`;
- `consent_required`: a model-backed step without both §7216 consents waits on inputs.

422 `formula_invalid` (E13's closed grammar, ADR-237). 403 `level_not_permitted`.

## 6. Audit events
Through the unit of work, identifiers and fingerprints only (DEC-60):
- `workbook_cell.edited`, `workbook_import.created`, `workbook_run.started`;
- `tax_ownership.replaced`, `allocation_structure.drafted`, `allocation_structure.proposed`
  (the agreement reader's proposal adopted, Pending approval), `allocation_structure.approved`
  (the person's own approved version after the L3 sign-off; T-05-T41, DEC-4701);
- `preparer_memo.draft_requested`, `preparer_memo.section_edited`.

Sign-offs, proposals and decisions write P-04's events. Each action lands in the activity catalogue with its build task.

## 7. Red services N provides (signatures)
- `tax.compute.entity.allocate(structure, periods, items) -> Allocation` (pure, golden-tested, CPA-reviewed);
- `tax.compute.entity.roll_capital(basis, beginning, movements) -> CapitalRoll`;
- `organisations.api.entity_consent_subjects(return_id) -> list[TriSubject]` (C19 for a partnership: both consents per partner set, OQ-2).

## 8. Versioning
| Version | Date | Notes |
|---|---|---|
| v1 | 2026-11-10 | stub (T-05-T06): 32 routes, 501, dark |
| v1 | 2026-11-13 | **frozen** (T-05-T46, DEC-4712): 33 routes (+ `POST …/allocation-structure/approve`); additions since the stub are additive fields only |

## T-05-T41 · the allocation structure (DEC-4701, DEC-4702)
- Versions are insert-only (`expected_version` = the newest version number read, else 409
  `structure_version_conflict`). A person's draft is Pending approval with its results stored;
  a manager or partner on the engagement drafts (`structure_editor_required`, 403).
- The agreement reader's proposal, once a person approves it, is adopted as a version Pending
  approval (`proposed_by: agent`); nothing is approved by the adoption.
- `GET` answers the additive fields `structure_id`, `sign_off_target_id`, `latest_version`,
  `method`, `convention`, `proposed_by`, `income`, `distributable`, `periods`, `partners`,
  `results`, `checks`, `gp_profit_percent`, `citation_ids` and `persisted` (False on a preview).
- `POST …/approve` is the L3 sign-off on `sign_off_target_id` with `seen_hash` through P-04
  (an agent, staff and the version's preparer are refused there), then the person's own
  `approved` version row and a run of the `capital` and `k1s` groups (none while a run is open).
- 04 Allocation, column D from row 2, holds the closed-books amount per segment that interim
  closing reads when the draft names none (written by T-05-T40's `interim_closing_706d`).

## T-05-T40 · import mode and the part-2 steps (DEC-4703, DEC-4704)
- `POST …/workbook/imports?kind=` takes the raw CSV or xlsx report (≤ 5 MB: 413
  `import_too_large`; `import_invalid` 422 lists sheet, row, column and code) and answers
  `import_id`, `kind` and the cells written; an open run is 409 `cells_locked_by_run`.
- Cells: 02 A–H from row 2 for a depreciation report (with a SUM total row), 08 F–H from row 2 for
  a state schedule; source `engine_import`, citation note "‹Depreciation report|State schedule›
  import ‹sha256[:12]› row ‹n›".
- 04 Allocation rows from 2: A period key (`p1`, `p2`), B start, C end, D the segment's amount.
- 06 D is the state amount (first state's apportionment); 08 J–L the state share per recipient
  and line.
- A step with nothing to read answers `failed` with its class and one issue
  (`run_step:<step>:<class>`, blocks final approval). `convention_706d` is the run's question step
  when the convention is not settled; its answer is the option key.

## T-05-T42 · sections, sign-offs and tie-outs (DEC-4705, DEC-4706)
- Sections (code): `trial-balance` (01, 03), `fixed-assets` (02), `allocation` (04),
  `capital-accounts` (05, 07), `schedule-k` (06, 09), `states` (08). Each has a stable
  `section_id` (`tax_workbook_sections`, 0860) and is the `tax_workbook_section` reviewable;
  its content hash is the SHA-256 of its sheets' cells (`seen_hash` = `sha256:<hex>`).
- `GET …/sections` adds `section_id`, `seen_hash` and `stale_levels`; tallies are the
  section's tie-outs (`tb_foots`, `capital_rollforward`, `item_l_m2`, `k1_sum_k`).
- `POST …/sections/{key}/sign-off` takes `level` `l1` (the preparer's), `l2` or `l3`, `seen_hash`,
  an optional `note` and `statement_version`; with an off tie-out and no note it is 409
  `tie_out_off` (`count`); with a note the sign-off records and the note is sealed beside it,
  audited `tie_out.off_acknowledged` with its hash only.
- After every terminal run state on a return's run, each off tie-out raises one `review_point`
  issue as the system (`tie_out:<key>`, `self_check`, resolved only by the system, `cell_range`
  links, a fixed-template note), reopened if it fails again; a passing one resolves.
- Item L ties the M-2 against the partners' ending capital on 05 (Schedule L line 21 is not on
  the workbook; recorded deviation from F8's wording).

## 9. Frozen v1 (T-05-T46, DEC-4712)
The freeze holds every model of `tax/workbook_contract.py` (`python -m abacus_tools.contracts
--check` fails a removed or retyped field, a field made required or a removed enum member;
additions pass). Consumers code against this section.

### 9.1 The cell store
- One `tax_workbook` per entity return (the return's work item); cells are review fields of
  target `tax_workbook` written only through `workbook_service.write_cells` (`review.record_value`,
  insert-only versions), each with its source: `formula`, `engine_import`, `tb_linked` or
  `human`. A run step never overwrites a cell a person wrote (`keep_human`).
- Sheet registry, Form 1065 (`SHEETS_1065`, frozen): 01 Trial Balance, 02 Adjustments (the
  depreciation import's rows, the screens' "Fixed Assets"), 03 Form Lines, 04 Allocation, 05
  Capital, 06 Schedule K, 07 M-2, 08 State, 09 K-1s. TXP-11's tab titles are the handoff's (02
  Fixed Assets, 03 Liabilities, 04 Partner Txns, 08 States); the server's titles above are the
  contract's and stand (recorded deviation; T-06 adds sheets, never renames).
- Addresses: `<sheet>!<column><row>` ("05!F2"); the long form `05 Capital!F2` is accepted.
- Layouts (code reads them; a consumer writes the same): 01 from row 2 A account, B name, C UTB,
  D AJE, E RJE, F ATB, then a total row; 02 A–H the asset rows plus a total row; 03 one row per
  mapped line; 04 from row 2 A period key, B start, C end, D amount; 05 from row 2 A partner, B
  beginning, C contributions, D distributions, E income share, F ending; 06 from row 2 A line, B
  label, C federal, D state; 07 B by M-2 line number; 08 A–C Form 8825 property, line, amount,
  F–H state, apportionment %, PTET, J–L recipient, line, state share; 09 one column per
  recipient from B, row 1 its name, rows matching 06.

### 9.2 The formula grammar and the DAG
ADR-237's closed grammar (references, ranges, cross-sheet references, + − × ÷, SUM, ROUND, IF,
MIN, MAX), parsed and evaluated by `workpapers.compute` (E13); never evaluated as text. A cell
edit recomputes its dependents synchronously up to 500, else 422 `recompute_too_large`.

### 9.3 The run plan
Provider `tax.entity_workbook` (P-10's plan-provider slot): ten steps in six groups (import, map,
compute, capital, apportionment, k1s), plan level = dependency depth; scopes `all`, `group`,
`task` (each with its dependants). `convention_706d` is a question step before
`interim_closing_706d` when no person settled the convention. Import mode for
`depreciation_register`, `bonus_eligibility`, `apportionment_ptet`, `state_k1s_k3s`. A step with
nothing to read answers `failed` with its class and one issue (`run_step:<step>:<class>`).

### 9.4 Schedules, the allocation model and K-1 drafts
- TB/TTB and tallies (T-05-T33), Schedule K with `analysis` (T-05-T34, T-05-T43), capital and M-2
  (T-05-T34), sections and tie-outs (T-05-T42).
- The allocation structure: insert-only versions with rungs and stored results; `GET`, `PUT
  …/draft`, `POST …/preview` (no persistence), `POST …/approve` (L3 then a `capital` + `k1s`
  re-run); E5 parts 1 and 2 compute (T-05-T41, T-05-T44's fields).
- The K-1 draft payload: 09's per-recipient shares by Schedule K line are the drafts; writing
  them into `k1_packages` (C10) and releasing are T-02's and T-04's, never this contract's.

### 9.5 Routes still answering 501 (their rows)
`GET …/workbook/export.xlsx` (T-05-T57); `GET …/issues` (T-05-T51); the memo routes and `GET
…/opportunities` (T-05-T54); `GET …/reconciliation` (T-05-T61). `PUT …/ownership` is named by
no later row and stays 501 (DEC-4737: its version store and what a replaced ownership does to an
approved allocation structure and the K-1 drafts are unplanned). Served since (S41 leftovers,
DEC-4737): `GET …/general-information` (entity name, form, year, the EIN's last four, the
profile's accounting method, the ladder's preparer, first reviewer and signer) and `GET …/partners`
(partners in order with the TIN's last four, periods grouped by date range, transfers with their
first clause citation, `version` 1, `tax_ownership.edit` when held); both through the offshore
mask. `POST …/mappings` was served by T-05-T37 (DEC-4629).


## T-05-T50 · the fix flow (DEC-4901, DEC-4902)
Additive (no route). An issue on an entity return (`record_type` `tax_return`, the form has a
workbook) is fixed through SHL-15's fix instructions: the tax fix runner proposes one
`workbook_cell_changes` proposal (C3) with a row per cell (`target_type` `tax_workbook`,
`field_key` `<sheet>!<cell>`, `before` and `after` as `{t, v}`, cause `fix_instructions`), decided
in SHL-10. On approval the cells are written as the approver's (`value_source` `human`), dependents
recompute, `workbook.fix_applied` is audited, the approver's checkpoint "Fix approved by <name>" is
saved and a `group` run of the fixed sheets' groups starts (it shows in `GET …/workbook-runs`). A
tie-out issue stays In progress until the re-run's tie-outs pass; the system resolves it.

## T-05-T51 · TXP-10's queue and actions (DEC-4903, DEC-4904)
`GET …/issues` answers (was 501): items with `section` (`waiting_on_client`, `review_points`,
`resolved` with `show_resolved`), `step`, `kind`, `priority`, `source_kind`, `category_path`,
`blocks`, `assignee` (person or agent), `cells` (linked ranges), `request_item_id`, `version`,
`created_at`, `allowed_actions`; `by_section`, `by_step`, `open_total` (the badge) and
`sections` count open issues before filters; `resolved_total` is Show resolved's count. New:
`GET …/issue-assignees` (team, Accrued Agent, client contacts); `POST …/issues/{id}/send-to-client`
(`{seen_version, contact_id, due_on}`; the issue's own client wording only; 409
`client_wording_missing`); `POST …/issues/{id}/reminders` (202, a follow-up draft from the
Reminder template; 409 `issue_not_sent`); `POST …/issues/{id}/resolve` (`{seen_version, note}`;
422 `resolution_note_required` when no approved fix closed it). Migration 0870.

## T-05-T52 · decision and gate kinds (DEC-4905, DEC-4906)
Additive (no route). C3 decision kind `basis_adjustment_election` (§754) (reserved `engagement_partner`; options
`elect_now`, `file_without`, `against`; context `transfer`, `due`, `difference`), raised by the
run after `interim_closing_706d` when the year has a transfer. Gate kinds: `tax_mapping_complete`,
`tax_allocation_approved`, `tax_fix_settled`, `tax_memo_approved`, `tax_run_questions_answered`.
C16 kinds `workbook_fix_applied` and `tax_memo_stale`; events `workbook.fix_applied` and
`tax_memo.went_stale` invalidate `engagement:<id>` and `work_item:<return id>`.

## T-05-T57 · Open in Excel (DEC-4908)
`GET …/workbook/export.xlsx?version=&sheet=` answers (was 501): the xlsx (`application/vnd.
openxmlformats-officedocument.spreadsheetml.sheet`, `Content-Disposition` attachment named
`<Entity>_<year>_<form>_Workbook_v<n>.xlsx`, `ETag` the SHA-256, `no-store`). Identical data gives
identical bytes; formulas are the closed grammar's, live; text is never a formula. 409
`export_blocked` while a run is open (the live workbook only); 404 `workbook_version` for an
unknown version. Audited `workbook.exported`.

## T-05-T54 · the memo service (DEC-4909, DEC-4910)
`GET …/memo` answers (was 501): `status` (`drafting`, `adopted`, `approved`, `stale`), sections
(`key`, `title`, `body`, `human_owned`, `version`), `seen_hash`, `stale_fields` ("ending capital
6,860,000 → 6,866,200"). `POST …/memo/draft` (202 `run_id`; 409 `consent_required`; no sections
named regenerates a stale memo's affected sections). `PATCH …/memo/sections/{key}` (409
`memo_version_conflict`). `POST …/memo/adopt` (L1) and new `POST …/memo/approve` (L2; 403
`preparer_cannot_approve`). `GET …/opportunities` answers. Event `tax_memo.went_stale`.

## Live since T-05-T61 (2026-11-14, DEC-4934)
`GET /v1/tax-returns/{id}/reconciliation` compares the engine's approved figures (engine keys
`schedule_k.<line>`, `k1.<partner_ref>.<line>`, `capital.<partner_ref>.ending`, `m2.<n>`, the
values an approved CCH import wrote on the return) with the workbook's, by code. Rows gain
`label` and `differs`; the response gains `accrued_label` ("Accrued tie-out (shadow)").
Approving an entity import raises one `engine_diagnostic` issue per difference
(`source_ref recon:<key>`, a figure-free title), each blocking final approval.

