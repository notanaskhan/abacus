# Closes · the close engine (v1)

| Field | Value |
|---|---|
| Version | v1 |
| Status | **stub** (C-01-T04 part 1, 2026-11-14; C-01-T05 part 2); every route answers 501 behind `closes.engine` until its build task; freezes at the end of S45 (C-01 §8), additive after |
| Provider epic | C-01 (SPEC-655) |
| Consumers | CLS-01, 02, 03, 04, 05, 06, 09, 10 and POR-11 (C-01 FE rows); C-02 (CLS-07, 08, 11, 12, 13 hosts and the Approved, Delivered and Locked guards), K-04 (close board provider), I-01 (HOME-01 count, HOME-02 gates), P-08 (portal home source), P-02 (search), W-02 (WB-01c run rows), K-02 (KNW-04a examples), G-03 (public reads, 2029) |
| Flags | `closes.engine` (firm routes), `closes.portal_requests` (portal questions), `closes.agent` (model modes); entitlement `closes` |
| Code | `backend/src/abacus/modules/closes/contract.py` (part 1), `closes/contract_work.py` (part 2) |
| Matrix | C-01-T02's rows in `docs/architecture/permission-matrix/closes.yaml`, `requests.yaml` (transaction questions) and `connections.yaml` (ledger sync) |

## 1. Who may call it
Every firm route answers, in order:
1. a client principal answers 404 (no firm close route is a portal route);
2. `closes.engine` off for the firm answers 404 (`feature_disabled`, AC-54);
3. a human-only route refuses anything but a live person with 403 (INV-1, AC-12): status moves, assignees, generate, run start and retry, plan edits, publish, request publish, draft from history, adopt, template import;
4. the route's one matrix action applies (walls first, 404: INV-3);
5. then 501 until its build task.

P-04's sign-off, issue, decision and proposal routes, P-06's request-item routes, A-06's C8 entry routes and P-10's run API are reused, not repeated here.

## 2. Part 1 — portfolio, record, runs, plans (C-01-T04)

| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/closes?period&status&preparer&reviewer&attest&q&cursor` | `close.read` | `CloseListOut` (items, four tiles, summary line) | T14 |
| `GET /v1/closes/running` | `close.read` | `RunningClosesOut` | T20 |
| `GET /v1/closes/{id}` | `close.read` | `CloseSummaryOut` with `allowed_actions` | T14 |
| `PUT /v1/closes/{id}/assignees` (If-Match) | `close.assign` | `CloseSummaryOut` | T14 |
| `POST /v1/closes/{id}/status` (If-Match) | `close.status_move` | `CloseSummaryOut`; 409 `accounts_not_reconciled`, `run_in_progress`, `transition_not_available` | T14 |
| `POST /v1/engagements/{id}/closes:generate` (Idempotency-Key) | `close.create` | `GenerateClosesOut`; 409 `work_item_exists` | T14 |
| `POST /v1/closes/{id}/runs` (Idempotency-Key) | `close_run.start` | `StartRunOut` (202) | T20 |
| `GET /v1/closes/{id}/runs` · `/runs/{n}` | `close.read` | `CloseRunsOut` · `CloseRunOut` (task groups) | T20 |
| `POST /v1/closes/{id}/runs/{n}/steps/{step}/retry` | `close_run.retry` | `CloseProcedureOut` (202; a new step row) | T20 |
| `GET /v1/clients/{cid}/close-plan?version` · `/versions` | `close_plan.read` | `PlanVersionOut` · `PlanHistoryOut` | T15 |
| `POST …/close-plan/drafts` · `PATCH …/drafts/{v}/rows/{rid}` · `POST …/drafts/{v}/rows` · `POST …/drafts/{v}/request-templates` | `close_plan.edit` | `PlanVersionOut` · `PlanRowOut` · `RequestTemplateOut`; 409 `stale_version` | T15 |
| `POST …/drafts/{v}/publish` | `close_plan.publish` | `PlanVersionOut`; 409 `unadopted_rows` | T15 |
| `POST …/drafts/{v}/request-publish` | `close_plan.request_publish` | `PlanVersionOut` (one C13 gate, QC-8) | T15 |
| `POST …/close-plan/draft-from-history` | `close_plan.draft_from_history` | `DraftFromHistoryOut` (202) | T30 |
| `POST …/drafts/{v}/rows/{rid}:adopt` · `…/rows:adopt-all` | `suggestion.resolve` | `AdoptOut` | T15 |
| `GET /v1/close-templates` · `POST /v1/close-templates:import` | `close_plan.read` · `close_template.import` | `CloseTemplatesOut` · `CloseTemplateOut` | T15 |

**Words.** Close statuses are the six canonical states (`close`); "On hold" is `close_flag.on_hold`, never a status (DF-23). Tiles: Approved counts under In review, Locked under Delivered (QC-6). Procedure statuses are `close_procedure`; plan versions `close_plan_version`; sync `ledger_sync` (C9 v2.1).

## 3. Consumer API (Python, C-01 §4.4)
- `closes.api.close_for(tenant, work_item_id) -> CloseFacts` (status, period, plan version, reconciled count, open issues, attest): C-02, K-04, I-01, P-08. Stub raises `NotImplementedYet` until T14.
- `closes.api.register_status_guard(to_status, guard)`: C-02's slot for `approved`, `delivered`, `locked`, one guard each. `status_guard(to)` answers 409 `transition_not_available` while none is registered (fail closed, AC-11).
- Later rows add `accepted_explanations`, `reconciled_accounts`, `procedure_statuses` and `sync_status` (T23, T25, T20, T17).

## 4. Part 2 — intake, accounts, reconciliation, review, flux, portal (C-01-T05)
Code: `closes/contract_work.py`. Firm routes answer as §1; a transaction question to a client also
needs `closes.portal_requests`. Refusal codes added: `open_items`, `statement_not_available`,
`question_template_required` (with part 1's, C-01 §4.3).

## 5. Intake (CLS-03)
| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/closes/{id}/requests?view=tree&q&status` | `close.read` | `RequestTreeOut` (counts, screening glyph, Linked (n), internal-only bank-feed rows QC-1) | T19 |
| `GET /v1/closes/{id}/questionnaire` | `close.read` | `CloseQuestionnaireOut` | T19 |
| `GET /v1/evidence-versions/{v}/close-summary` | `close.read` | `IntakeSummaryOut` (code figures with `sheet_cell` citations; label `summarized_by_agent` or `totals_from_file`, DV-3) | T19 |

Incorporate, undo, return and on-behalf upload stay P-06's `request_item.*` routes.

## 6. Accounts and schedules (CLS-04)
| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/closes/{id}/accounts?show_zero&group_by` | `close.read` | `AccountTreeOut` (rolls up in code; contra flag) | T21 |
| `GET …/accounts/{acct}/register?cursor` | `close.read` | `RegisterOut` (`ledger_line` citable rows) | T21 |
| `GET …/accounts/{acct}/workpaper` · `…/workpaper.xlsx` | `close.read` | `WorkpaperOut` (no Post control, DV-1; `recording` "Recorded in QuickBooks") · bytes | T21 |
| `POST …/accounts/{acct}/arrangements` · `PATCH /v1/arrangements/{aid}` | `arrangement.edit` | `ArrangementOut` (a new version per edit) | T21 |
| `POST /v1/register-lines/{ref}/recategorization-proposals` | `proposed_entry.create` | `ProposalRefOut` (to SHL-10) | T21 |

## 7. Reconciliation (CLS-05)
| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/closes/{id}/reconciliations/{acct}` | `close.read` | `ReconciliationOut` (both sides, items, statement lines with regions, sign-off blockers, `engine_version`, `inputs_hash`) | T23 |
| `POST /v1/reconciliations/{rid}/items/{iid}/resolve` | `reconciliation.resolve_item` | `ReconcilingItemOut` (note required; a person's) | T23 |
| `GET /v1/reconciliations/{rid}/items/{iid}/entry-draft` | `close.read` | `EntryDraftOut` (a suggestion) | T23 |
| `POST /v1/closes/{id}/entries` | `proposed_entry.create` | `ProposalRefOut` (through `adjustments.api.propose_entry`) | T23 |

L1 sign-off is P-04's `POST /v1/sign-offs` on target `reconciliation` (409 `open_items`).

## 8. Review and transaction questions (CLS-06; C5 additive)
| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/closes/{id}/issues?class&include_resolved` | `close.read` | `CloseIssuesOut` (open = badge; notes never count) | T24 |
| `POST /v1/issues/{iid}/transaction-questions` | `transaction_question.send` | `TransactionQuestionOut`; 409 `question_template_required` | T24 |

Issue actions stay P-04's human-only routes.

## 9. Flux (CLS-10)
| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/closes/{id}/flux?basis` · `…/flux.xlsx` | `flux.read` | `FluxSetOut` · bytes | T25 |
| `POST /v1/analytic-lines/{lid}/explain` | `flux.explain` | `StartedRunOut` (202; mode `flux`) | T30 |
| `PUT /v1/analytic-lines/{lid}/explanation` (If-Match) | `flux.edit` | `FluxLineOut` | T25 |
| `POST /v1/analytic-lines/{lid}/accept` (If-Match) | `flux.accept` | `FluxLineOut` (Manager or Partner) | T25 |

## 10. Portal questions (POR-11)
Only a client principal; `closes.portal_requests` off answers 404; inside the grant
(`scope_only`). The DTO carries the client wording and context line only: never the issue, its
severity or the agent (QC-9, AC-47).

| Method · path | Action | Response | Build task |
|---|---|---|---|
| `GET /v1/portal/closes/{close_id}/questions` | `transaction_question.read_own` | `PortalQuestionsOut` | T27 |
| `POST /v1/portal/questions/{qid}/answer` | `transaction_question.answer` | `PortalQuestionOut` | T27 |

The close-intake binder reads through P-08/R-01's `GET /v1/portal/binders`, and Mark as Done through P-06's binder action.
