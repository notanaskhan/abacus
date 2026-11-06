---
id: TASK-3339
title: A-06-T28: disclosure checklist import, publish and the 142 items
spec: SPEC-000  # row (A-06-T28)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T28
branch: s28r-a06-t28
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
The firm's checklist loads as content through its import route; the slice loads ASC 962's 142 synthetic items.

## Plan
- `methodology/disclosure_checklists.py`; live import and publish routes; `--slice completion`.

## Progress log
- 2026-11-06: built. `tests/unit/methodology/test_a06t28_checklist_import.py`, `tests/integration/test_a06t28_checklist_load.py` and the C11 contract suite pass locally.

## Decisions made during this task
DEC-2330
