---
id: TASK-6111
title: "A-05-T54 EBP-07 service and Form5500TieOut: Schedule H against AUD-20 by code, Part IV 4a, Note 8 reconciling"
spec: SPEC-000  # row (A-05-T54)
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: A-05
plan_key: A-05-T54
branch: s30-a05-t54
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
A-05 F9: the tie-out starts on the draft Form 5500, maps Schedule H lines by plan year to FS captions from AUD-20, classifies differences by code (tie, reconciling item, inconsistent), checks Part IV against EBP evidence.

## Plan
- `assurance/compute/ebp/form5500.py`: pure engine (classify, amounts_by_line, part_iv_4a, sums_to, inputs hash).
- `reporting/fs_captions.py` + api: `statement_caption_amounts(tenant, work_item)` from AUD-20's current statement version.
- `assurance/ebp_form5500.py`: `record_draft_received` (supersedes, emits `ebp.form5500.draft_received`), `on_draft_received` (dispatches the workflow), `tie_out` activity body (newest published taxonomy effective for the plan year, code classification, human classifications kept, 4a against `ebp_late_remittances` on line 4a), `document_reconciling_item` (parts must foot to the difference).
- `assurance/form5500_workflow.py`: `Form5500TieOut` (background); recorder `abacus_tools/workflows/record_form5500_tieout.py` and `tests/workflows/test_form5500_tieout_replay.py`.
- `assurance/api.py`: workflow, activity, subscription.
- Tests: `tests/unit/assurance/test_a05t54_form5500_tieout.py`.

## Progress log
- 2026-11-08: built. Written, not run (tests at the end review). ruff and pyright clean; the app and worker import.

## Decisions made during this task
DEC-2709
