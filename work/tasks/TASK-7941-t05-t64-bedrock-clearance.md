---
id: TASK-7941
title: "T-05-T64: Bedrock clearance for tax.account_mapper, tax.agreement_reader, tax.memo_drafter and the recommender modes"
plan_key: T-05-T64
spec: SPEC-651  # T-05 §6
acceptance_criteria: [AC-F13]  # all four show client_data cleared with committed Bedrock reports
risk_zone: red
status: in-review
branch: t05-t64-bedrock-clearance
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
The clearance run for the four entity capabilities: full suites in the evaluation account,
HMAC-signed reports, baseline cost rows, route parity under 90 days.

## Plan (red)
- `abacus_tools/evals/tax_entity_real.py` (new): clearance, signed report, `real_main`;
  `__main__` routes the four suites' real runs to it.
- `evals/baselines.yaml` (protected): four rows, each the spec's budget.
- Tests: `backend/tests/unit/evals/test_t05t64_entity_clearance.py`.
- Rollback: revert.

## Partial
- No committed Bedrock report, so no capability shows `client_data: cleared` yet: the evaluation
  account's loop is not wired (as T-04-T43, P-10-T46, I-02-T20). The plan's Jul 10 shadow needs it.

## Progress log
- 2026-11-14: built; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4936 | one runner, frozen thresholds, spec budgets as baselines, Bedrock + parity only | no |
