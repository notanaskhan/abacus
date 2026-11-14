---
id: TASK-8008
title: "C-01-T08: C9 v2.1 consumer contract tests"
spec: SPEC-655
acceptance_criteria: []
risk_zone: red
status: in-review
branch: c01-t08-c9-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T08
---

## Objective
C9 v2.1 consumer contract tests.

## Plan
1. [x] `backend/tests/contracts/c09_ledger/` v2.1 additions: account-tree, monthly-balance, register-line and sync-status shapes; no write route on connections; flag-off 404.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built: `backend/tests/contracts/c09_ledger/test_c09_v21_consumers.py` and the fixture `fixtures/copperleaf_2026_08_tree.json` (totals and the accounts SPEC-655 names, verbatim). Field drift for CLS-04, CLS-05 and CLS-10 reads, the four ledger reads exported, refusal codes, money Decimal and `confidential`, the fixture footing in code, the two sync routes with one action and a 501 each, and no write-shaped name in C9 v2.1. Not run (end pass).
- **Partial.** A walled entity answers 404 (no `not_visible` code). The full Copperleaf chart arrives with the figure book (C-01-T13).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
