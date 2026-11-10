---
id: TASK-6511
title: "T-04-T09: flags tax.review_workspace, tax.individual_workpapers, tax_agents.enabled"
spec: SPEC-649
acceptance_criteria: [AC-1]  # the row's acceptance (AC-flags)
risk_zone: red
status: in-review
branch: s33-t04-t09
worktree: /Users/ayushkbhatia/Accrued/abacus-s33
created: 2026-11-09
updated: 2026-11-09
plan_key: T-04-T09
---

## Objective
T-04's three flags, boolean and default off; every RW-1/WS-1 route answers 404 while off.

## Plan (red)
1. `feature-flags/tax.yaml`: the three flags (DEC-137 override on the build clock).
2. `tax/workspace_contract.py`: RW-1 routes read `tax.review_workspace`, WS-1 routes
   `tax.individual_workpapers`, run-starting routes `tax_agents.enabled` and the workspace flag;
   a client principal 404s; then 501 until each build row.
Rollback: revert.

## Progress log
- `2026-11-09` — Built; not run (end pass). The flag-off designed states are the screens' (T-04-T12,
  T13: flag-off scenarios).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3111 | Which routes each T-04 flag gates | no |
