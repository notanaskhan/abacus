---
id: TASK-3309
title: P-11-T26 form-extraction framework and IRS notice header maps
spec: SPEC-000  # row (P-11-T26)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T26
branch: s28-p11-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"The Whitley CP2000 yields CP2000, TY2024, 753.01 and respond by Sep 23, 2026, the Santos CP14 photo fixture yields its eight header fields, and an obscured date is recorded low_confidence, never guessed."

## Plan
- `evidence/form_extraction.py`: identify, label-anchored extract, confidence as the minimum of the words', `extract_version`.
- `evidence/forms/<form>/2024.yaml`: CP2000, CP14, CP501, CP503, CP504.
- `FormExtractionWorkflow`, `forms.extract`, the `evidence_text.ready` subscriber.
- `Word.confidence`, written to the sealed layer only when not 1.0.
- Tests: unit; replay history recorded at the end pass (`record_form_extraction`).
- Rollback: flag `evidence.form_extraction` off; no schema.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2308
