---
id: TASK-6822
title: "T-04-T29 (partial): the issue detail's live read side for TAX-06 (fix instructions, fix run, explanations)"
spec: SPEC-649
acceptance_criteria: [AC-4.3, AC-4.4, AC-4.5]
risk_zone: green
status: in-review
branch: s36-t04-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: T-04-T29
---

## Objective (row)
Fixture-to-live swap for TAX-04, TAX-05, TAX-06, TAX-07 and TXI-01 on staging: live RW-1 and
WS-1 routes, SSE invalidation topics for return counts with polling fallback, blocked states from
409 blockers, DEC-24 Undo for approvals.

## Built (the part buildable now)
- `GET /v1/issues/{id}` now fills `fix_instructions`, `fix_run` and `explanations` from T-04-T31's
  `issue_runs`, `issue_fix_proposals` and `issue_explanations`:
  - `review/issue_runs.issue_run_facts`;
  - `review/contract._issue_runs_out`;
  - citation chips labelled through the field-citations reader;
  - the run's state from `agents.api.run_v2_status` (new, RLS-scoped).
  This is the live data SHL-15 a', a'' and d, and TAX-06's detail, need.
- Test: `tests/unit/review/test_t04t29_issue_detail_runs.py`.

## Partial (not built here)
- The front-end swap of TAX-04/05/06/07 and TXI-01 to live (the screens are still fixture-mode in
  `routes/firm/tax-review.tsx`).
- SSE invalidation topics for return counts.
- The 409 blocker states.
- DEC-24 Undo for approvals.
- The staging walk. Staging is not up, and the screens' live hosts are a front-end row of their
  own size.
- `suggestion` on the detail stays null: a code suggester slot (T-04-T31's
  `suggested_instruction`) needs a person-side read of the return's boxes.

## Progress log
- `2026-11-11` — Built the backend half (S36). Test written, not run (end pass).
