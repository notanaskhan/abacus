---
id: TASK-8838
title: "T-08-T14: Standards runs"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-t08t14
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: T-08-T14
---

## Objective
Running v4 on six 1065s yields 4 passed and 2 with exceptions, Ridgeline's two link to existing issues so its count stays 11, and Marlowe's three are created.

## Done
- tax/standards_runs.py (start, rerun, StandardsRunWorkflow + activities, tie-out checks, issue link/raise dedupe, progress events, confirm, reads)
- methodology checklist_version + register_check_code export
- review open_issue_for_ref
- TAX-14 routes live
- activity_reviewed
- tests/unit/tax/test_t08t14_standards_runs.py
- DEC-5840

## Progress log
- `2026-11-20` — Plan (amber): service, workflow, routes, tests; no migration (0961); rollback = revert. Workflow replay history at end pass. Tests at the end pass.
