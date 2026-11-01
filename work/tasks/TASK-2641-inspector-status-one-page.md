---
id: TASK-2641
title: The build's Inspector gate reads one scan status, not one per findings page
spec: SPEC-000  # build.yml inspector job (Q-01; S8 wave B security review)
acceptance_criteria: [AC-1]  # a finished scan (ACTIVE or COMPLETE) is recognised whatever the findings count
risk_zone: green
status: in-review
epic: Q-01
plan_key: Q-01-T18
branch: s21-inspector-status
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Three main builds failed at the Inspector gate with "scan status 'ACTIVE'" (DEC-1683).

## Scope
`.github/workflows/build.yml`: the status read takes one page and one line;
`backend/tests/unit/tools/test_security_review_workflows.py` pins it. Rollback: revert.

## Progress log
- 2026-11-01: built; workflow tests passed.
