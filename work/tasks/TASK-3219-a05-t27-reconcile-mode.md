---
id: TASK-3219
title: A-05-T27 mode ebp_reconcile on the section drafter
spec: SPEC-640
acceptance_criteria: [AC-23]
risk_zone: red
status: in-review
epic: A-05
plan_key: A-05-T27
branch: s26-a05-t27 (stacked on s26-n04-t07)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
The reconcile run drafts each document's totals with citations and **proposes** exceptions; code
supplies every sum (A-05 F5: the late remittance and the cutoff receivable are proposed and none
raised).

## Plan (red)
- Prompt `workpapers.section_draft.ebp_reconcile@v1`.
- Spec v8.
- `assurance/ebp_reconcile.py`: `reconcile_inputs` gives the contribution documents (masked) and
  code's register totals as facts.
- Mapping registered. `_specs.py` and `_eval_suites.py` regenerated.
- Test: `tests/unit/assurance/test_a05t27_reconcile_mode.py`.

## Progress log
- 2026-11-03: built. The eval case set for the mode is the S24 EBP suite's to extend (A-05-T14's
  baselines); no eval run (`make evals` costs money). Tests at the S26 end review.

## Decisions made during this task
DEC-2219.
