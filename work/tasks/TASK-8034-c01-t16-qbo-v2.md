---
id: TASK-8034
title: "C-01-T16: QuickBooks Online read connector v2 (red)"
spec: SPEC-655
acceptance_criteria: [AC-32, AC-33, AC-34]
risk_zone: red
status: in-review
branch: c01-t16-qbo-v2
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T16
---

## Objective
The close engine's QuickBooks Online reads: accounts with Classification, AccountType and
AccountSubType; a TrialBalance report per month; GL detail normalised to register lines with
the offset account; CDC through `changes_since`; per-realm throttling and back-off (ADR-043);
metered call counting; the minor-version pin; no write method (CONN-001).

## Plan (red: written before the build)
1. **Protected** `connections/connector.py`: widen `Dataset` (additive) and add `RateLimited`.
   Needs Ayush's approval (DEC-5022).
2. `connections/qbo_throttle.py` (new): per-realm window and concurrency, provider breaker,
   Retry-After parsing.
3. `connections/connectors/quickbooks_online.py`: capabilities (four datasets, incremental),
   `_get` inside the throttle with the call counter and 429 → `RateLimited`, `pull` per dataset
   (accounts paged by cursor, `gl_detail` by month with the register columns, TrialBalance for a
   month), `changes_since` over `/cdc`.
4. `connections/qbo_format.py`: `parse_qbo_accounts`, `parse_qbo_general_ledger` with the
   hostile-content guards of the TrialBalance parser.
5. Tests: `tests/unit/connections/test_c01t16_qbo_v2.py`; the QBO conformance harness in
   `test_qbo_connector.py` covers the new datasets; synthetic fixtures
   `qbo_accounts_synthetic.json`, `qbo_general_ledger_synthetic.json`, `qbo_cdc_synthetic.json`.
Rollback: revert; the datasets are only pulled by C-01-T17's workflow (not built yet). No
migration (0882 already widened `sync_runs.dataset`).

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010); plan written above before building.
- `2026-11-15` — Built as planned. Every request is still a GET to the API host (or the two
  OAuth POSTs declared as reads); the query language string is built from integers only. Not
  run (end pass: unit suite, conformance, write-interception harness, security review of the
  red diff).
- **Partial.** Recording the new datasets (ledger_accounts, monthly snapshots, register lines)
  and the meter's monthly budget are C-01-T17's `LedgerSyncWorkflow`; a live sandbox run needs
  the Intuit sandbox company (F-09-T05). The fake connector keeps `trial_balance` only.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5022 | v2 datasets, throttle and breaker, CDC returns dataset names; protected contract edit | no |
