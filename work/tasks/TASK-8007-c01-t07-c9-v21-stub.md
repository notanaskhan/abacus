---
id: TASK-8007
title: "C-01-T07: C9 v2.1 additive stub — monthly CAS ledger datasets and sync facts"
spec: SPEC-655
acceptance_criteria: []
risk_zone: red
status: in-review
branch: c01-t07-c9-v21-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T07
---

## Objective
C9 v2.1 additive stub — monthly CAS ledger datasets and sync facts.

## Plan
1. [x] `ledger/cas_contract.py`: AccountTreeNode (classification, type, subtype, contra), MonthlyBalance, RegisterLine (ledger_line citable ref), PeriodComparison, SyncStatusFacts VMs with classification `confidential`.
2. [x] `ledger.api` signatures `account_tree`, `monthly_balances`, `register_lines`, `compare_periods` raising NotImplemented-style 501 at routes; `GET/POST /v1/client-entities/{eid}/ledger-sync` 501 behind `connections.ledger_sync`.
3. [x] C9 v2.1 section in `docs/contracts/c09-ledger.md`. No write method (CONN-001).
Rollback: revert; additive.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built: `ledger/cas_contract.py` (LedgerAccountOut, MonthlyBalanceOut, AccountTreeOut, RegisterLineOut, PeriodComparisonOut; `account_tree`, `monthly_balances`, `register_lines`, `compare_periods` raising NotImplementedYet; refusals `stale_source`, `period_not_available`), re-exported from `ledger.api`; `connections/ledger_sync_contract.py` (GET/POST `/v1/client-entities/{eid}/ledger-sync` behind `connections.ledger_sync`, `ledger_not_connected`, `meter_budget_exhausted`); C9 v2.1 section in `c09-ledger.md`. The generated client is regenerated here for all three stubs (T04, T05, T07).
- **Partial.** The stub answers 501, not Copperleaf fixtures: the footing fixtures (assets 539,055.45 = liabilities 163,543.05 + equity 375,512.40) live with the consumer tests (T08) and the FE fixture handlers (T12). A walled entity answers 404 rather than a separate `not_visible` code (no existence leak).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
