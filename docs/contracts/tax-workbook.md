# Tax workbook · entity returns (v1)

| Field | Value |
|---|---|
| Version | v1 |
| Status | stub (T-05-T06, 2026-11-10): every route answers 501 under its one action, dark behind `tax.entity_workspace` |
| Provider epic | T-05 (SPEC-651) |
| Consumers | TXP-00, TXP-01, TXP-02, TXP-05, TXP-06, TXP-07, TXP-10, TXP-11 (T-05 FE rows); T-06 (TXP-03, 04, 08, 09 reuse the reads); T-08 (TAX-10 two-year) |
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

