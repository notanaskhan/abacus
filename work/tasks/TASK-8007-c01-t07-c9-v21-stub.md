---
id: TASK-8007
title: "C-01-T07: C9 v2.1 additive stub — monthly CAS ledger datasets and sync facts"
spec: SPEC-655
acceptance_criteria: []
risk_zone: red
status: todo
branch: c01-t07-c9-v21-stub
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T07
---

## Objective
C9 v2.1 additive stub — monthly CAS ledger datasets and sync facts.

## Plan
1. [ ] `ledger/cas_contract.py`: AccountTreeNode (classification, type, subtype, contra), MonthlyBalance, RegisterLine (ledger_line citable ref), PeriodComparison, SyncStatusFacts VMs with classification `confidential`.
2. [ ] `ledger.api` signatures `account_tree`, `monthly_balances`, `register_lines`, `compare_periods` raising NotImplemented-style 501 at routes; `GET/POST /v1/client-entities/{eid}/ledger-sync` 501 behind `connections.ledger_sync`.
3. [ ] C9 v2.1 section in `docs/contracts/c09-ledger.md`. No write method (CONN-001).
Rollback: revert; additive.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
