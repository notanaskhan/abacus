---
id: TASK-8435
title: "A-08-T22: rest: the SSARS FS row reads the statements package"
spec: SPEC-657
acceptance_criteria: [AC-7]
risk_zone: green
status: in-review
branch: s48r-ssars-fs-row
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T22
---

## Objective
The SSARS rail's FS row always read not_started. It now reads the work item's financial-statements package state from reporting: not_started, draft, out_of_date or published.

## Plan (green)
1. reporting.statements.package_state(tenant, work_item_id) over current_of; exported from reporting.api.
2. ssars.workspace uses it for the fs row.
3. Unit test over the six document/version shapes.

## Progress log
- `2026-11-17` — Built (S48 rest). The state words are the registry's (not_started, draft, out_of_date, published); out_of_date wins over published, as the version no longer matches the trial balance or the recorded entries. Gates and tests run once at the S48 end pass (build first, test last).
