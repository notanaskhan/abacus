---
id: TASK-5143
title: P-11-T29 OCR conformance suite, CI half
spec: SPEC-000  # row (P-11-T29)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T29
branch: s29-p11-t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
A code-only run on FakeOcr over the synthetic corpus that blocks merges.

## Plan
evals/ocr_extraction/suite.yaml with the plan's thresholds; tests/unit/evidence/test_ocr_extraction_suite.py.

## Progress log
- 2026-11-06: built. 7 pass. Nightly real-Textract half needs staging and stays open.

## Decisions made during this task
None.
