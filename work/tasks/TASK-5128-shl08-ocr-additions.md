---
id: TASK-5128
title: "P-11-T31 SHL-08 OCR additions: page text source, low-confidence notes, refusal and retry"
spec: SPEC-000  # row (P-11-T31)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T31
branch: s29-p11-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
SHL-08 says how a page's words were read, which boxes read low, and when the OCR gate refused, with a retry for someone who may ask for one.

## Plan
OcrNotes above the viewer well. Manifest pages fill text_source and ocr from evidence_pages and the latest refused ocr_runs row. `evidence.ocr_retry` offered when the gate refused and the flag is on.

## Progress log
- 2026-11-06: built. OcrNotes.test.tsx and tests/unit/test_viewer_page_ocr.py written; held for the end pass.

## Decisions made during this task
DEC-2424
