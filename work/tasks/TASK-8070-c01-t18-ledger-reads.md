---
id: TASK-8070
title: "C-01-T18: Ledger read API for closes: tree, balances, register, compare, citations (red)"
spec: SPEC-655
acceptance_criteria: [AC-5, AC-6, AC-9]
risk_zone: red
status: in-review
branch: c01-t18-ledger-reads
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: C-01-T18
---

## Objective
Serve C9 v2.1 for closes: the month's account tree with natural-sign balances (footed in code),
monthly balances, the register a page of 200 at a time, a period comparison, a month tie of the
register against the trial balance movement, register-row `ledger_line` citations and the
`ledger.read_transactions` C17 tool.

## Plan (red: written before the build)
1. `ledger/cas_reads.py`: `account_tree`, `monthly_balances`, `register_lines` (≤ 200, cursor =
   line number), `compare_periods`, `month_tie`, `foots`, `register_row` (for the citable).
   `cas_contract.py` keeps the shapes and delegates (lazy import).
2. **Protected** `evidence/citations/ledger_line.py`: optional `register_line` in the locator; a
   register row verifies value (net or side) and quote (payee or memo); old locators unchanged
   (`exclude_none`). Needs Ayush's approval (DEC-5057).
3. `ledger/agent_tools.py`: `ledger.read_transactions` (rows carry `id` = `<snapshot>:<line>`;
   payees and memos untrusted). `ledger.compare_periods` already exists (P-10-T28).
4. Tests: `tests/integration/test_c01t18_ledger_reads.py`.
Rollback: revert; nothing outside closes reads the monthly sets yet.

## Progress log
- `2026-11-15` — Planned at the S46 kickoff (#2053); plan written above before building.
- `2026-11-15` — Built (DEC-5057). Import check clean (the C17 registry refused a paginated
  shape and an id-less row: fixed by an own cursor and `id`). Tests run at the end pass.
- "Month-scoped validation in general_ledger.validate_gl" is `cas_reads.month_tie` plus the
  register footing in `month_ledger` (C-01-T17): `general_ledger.py` (protected) is unchanged.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5057 | Natural signs; foot rule with the unclosed result; register-row citations by monthly snapshot and line | no |
