---
id: TASK-8822
title: "Q-05-T18: Inspections, findings and the annual evaluation"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-q05t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: Q-05-T18
---

## Objective
Selecting Sterling Freight with Thomas Whitcombe answers 422 inspector_not_objective, the five findings foot to 3 + 2, and conclusion stays 409 until all six inspections conclude.

## Done
- practice/inspections.py: cycles, candidates (deterministic risk score from the published selection rule, ties by seed; not-objective people per candidate), plan (422 inspector_not_objective; issues read-only grants to due + 30 days), start, conclude (revokes grants), findings (record with sealed title, update root cause/remediation/owner/due, QM owner evaluation, remediate, remediation to-do through P-05 with a finding link), annual evaluation (checklist, request conclusion → 409 inspections_open, else the firm-scope qm_annual_evaluation card for the QM owner)
- engagements.inspectable_work_items; identity api exports for grants
- 16 quality routes wired; reviewed audit actions; unit tests

## Progress log
- `2026-11-20` — Plan (amber): service over 0963 tables, routes; rollback revert (no migration). The register/objectives/imports/risk-review stubs (Q-05-T08 remainder) are built in the Q-05 sweep PR.
