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
| Propose a mapping | `POST /v1/tax-returns/{id}/mappings` | `account_mapping.edit` (the plan's `account_mapping.propose` once A-03 adds it) |
| Schedule K | `GET /v1/tax-returns/{id}/schedules/k?view=&version=` | `workbook.read` |
| Form 8825 by property | `GET /v1/tax-returns/{id}/schedules/k/lines/{line}/breakdown` | `workbook.read` |
| Capital accounts | `GET /v1/tax-returns/{id}/capital-accounts?view=&version=` | `workbook.read` |
| Schedule M-2 | `GET /v1/tax-returns/{id}/schedules/m2?variant=` | `workbook.read` |
| Allocation structure | `GET /v1/tax-returns/{id}/allocation-structure?version=` | `allocation_structure.read` |
| A new structure draft | `PUT /v1/tax-returns/{id}/allocation-structure/draft` | `allocation_structure.edit` |
| Preview without saving | `POST /v1/tax-returns/{id}/allocation-structure/preview` | `allocation_structure.read` |
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
- `tax_ownership.replaced`, `allocation_structure.drafted`;
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
