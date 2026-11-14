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
See §5 onward (added by C-01-T05).
