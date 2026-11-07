---
id: TASK-6010
title: "P-11-T30 masks burned on OCR pages, offshore and walled readers refused"
spec: SPEC-000  # row (P-11-T30)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: P-11
plan_key: P-11-T30
branch: s29l-p11-t30
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Every refusal path and the no-unmasked-pixel property on OCR pages are proven by tests written outside the implementing session.

## Plan
tests/unit/evidence/test_p11t30_ocr_masks_burned.py: each synthetic scanned page read by FakeOcr from its recorded layer, identifiers detected on the OCR words, burned by previews.render_masked; every pixel inside each detected box is the page's background in an RGB image while the clean render had ink there; a face with no identifier renders unchanged; the corpus faces with a taxpayer ID are named. tests/unit/evidence/test_p11t30_ocr_reader_refusals.py: an offshore reader gets 403 on a page image before anything is read, an onshore one the masked page, a walled version 404 on page, text and regions for both, a client principal refused first. No production change. Rollback: revert.

## Progress log
- 2026-11-07: built. Both files pass (11), pyright clean.

## Decisions made during this task
None.
