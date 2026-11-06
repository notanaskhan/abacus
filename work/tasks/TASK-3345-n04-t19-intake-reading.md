---
id: TASK-3345
title: N-04-T19 an intake leaves extracting, and extract runs for unmapped notices
spec: SPEC-000  # row (N-04-T19)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T19
branch: s28r-n04-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Call the responder's `extract` from intake (DEC-2313), and give intakes a way out of `extracting`.

## Plan
- `notices/intake_reading.py`: subscribers on `extracted_fields.recorded`, `upload_checks.recorded` and `ocr_run.refused`.
- `evidence.api`: `form_is_known`, `recorded_form_fields`, `masked_pages`.
- `extract_fields` returns the run id.

## Progress log
- 2026-11-06: built. `tests/integration/backfill/test_n04t19_intake_reading.py` (5) with worker, notices and agents suites: 901 passed. The model call and `form_is_known` are stubbed, so no test runs a real extraction from a page to an intake.

## Decisions made during this task
DEC-2334
