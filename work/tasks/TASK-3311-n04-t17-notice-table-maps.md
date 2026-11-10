---
id: TASK-3311
title: N-04-T17 CP2000 proposed-changes and payer maps, CP14 amounts
spec: SPEC-000  # row (N-04-T17)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T17
branch: s28-n04-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"The Whitley CP2000 yields interest 412.00 to 3,532.00 and both payers with regions, the Santos CP14 yields its amounts, and an obscured value is recorded low_confidence, never guessed."

## Plan
- `form_extraction.py`: `TableMap`, `extract_table`; each cell its own field with its box.
- `forms/cp2000/2024.yaml`, `forms/cp14/2024.yaml`: `tables`; map versions bumped.
- Goldens on the corpus land with P-11-T28.
- Rollback: the previous maps; flag `evidence.form_extraction`.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2310
