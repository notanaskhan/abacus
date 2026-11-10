---
id: TASK-5139
title: P-11-T30 Independent tests of OCR refusals
spec: SPEC-000  # row (P-11-T30)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-11
plan_key: P-11-T30
branch: s29-p11-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Every gate refusal fails closed, in order; retry is a person's; no page text in logs.

## Plan
tests/unit/evidence/test_p11t30_ocr_independent.py; bytes unchanged stays in test_p11t25_ocr_run.py.

## Progress log
- 2026-11-06: built. Passes. Masks burned on OCR pages, offshore refusal until masked, and walls on fields need Postgres and object storage: end pass adds them to the integration set or records them as open.

## Decisions made during this task
None.
