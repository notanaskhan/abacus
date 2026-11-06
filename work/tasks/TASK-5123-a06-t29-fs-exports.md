---
id: TASK-5123
title: A-06-T29 SUM and checklist workbooks, the management-approval event; send-draft waits for C10
spec: SPEC-000  # row (A-06-T29)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T29
branch: s29-a06-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Deterministic SUM and checklist XLSX with a formula guard, and the fs.approved_by_management event. Render and send as far as C10's stub allows.

## Plan
kernel/safe_xlsx.py; statements.checklist_workbook and export route; sum_service.sum_workbook and route; FsApprovedByManagement. Rollback: revert.

## Progress log
- 2026-11-06: built. `backend/tests/unit/reporting/test_a06t29_exports.py` written, not run (end pass). Pyright, ruff, banned patterns clean.

## Decisions made during this task
DEC-2419
