---
id: TASK-8828
title: "T-06-T37: Final-approval blocker: form-preview diagnostics"
spec: SPEC-702
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-t06t37
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-06-T37
---

## Objective
With a blocking diagnostic open the POST answers 409 blocking_diagnostics, and the eligibility read lists the reason TAX-11 shows on the disabled button.

## Done
- tax/form_preview_blockers.py provider (engine error diagnostics, Item L vs Schedule L line 21, §754 pending)
- approval.approve raises BlockingDiagnostics for diagnostic codes
- BLOCKER_WORDS for each code
- registered at tax api import
- tests/unit/tax/test_t06t37_form_preview_blockers.py
- DEC-5830

## Progress log
- `2026-11-20` — Plan (red): provider module, approval guard, words, registration, unit tests; rollback = revert the PR (no migration). Tests run at the end pass.
