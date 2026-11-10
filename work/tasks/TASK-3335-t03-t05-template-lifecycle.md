---
id: TASK-3335
title: T-03-T05 organizer template lifecycle and the editor's wall
spec: SPEC-000  # row (T-03-T05)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: T-03
plan_key: T-03-T05
branch: s28r-t03-t05
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Close T-03-T05's recorded partial (DEC-2241): template detail, owner, draft, discard, diff, owner-only publish for a tax year, `questionnaire_from_template`, BND-02's badge.

## Plan
- `requests/organizer_lifecycle.py`; publish and attach in `questionnaires.py`; live routes in `questionnaire_editor_contract.py`.
- Fix the editor's wall: read and save narrow to the binder's engagement.

## Progress log
- 2026-11-06: built. `tests/integration/test_t03t05_template_lifecycle.py` plus contract, audit, app-gate and route-introspection suites: 1,782 passed locally.

## Decisions made during this task
DEC-2370
