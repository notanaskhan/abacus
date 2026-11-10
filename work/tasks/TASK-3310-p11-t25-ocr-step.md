---
id: TASK-3310
title: "P-11-T25 UploadProcessing OCR step: normalise, read, seal, publish"
spec: SPEC-000  # row (P-11-T25)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T25
branch: s28-p11-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-05
updated: 2026-11-05
---

## Objective
"A scanned W-2 at a flagged firm gets OCR words, a masked box a and a page offshore members can open, with the flag off the page stays not_scannable, and the version's bytes and fingerprint never change."

## Plan
- `evidence/ocr_normalise.py` (isolated child): EXIF, HEIC, multi-page TIFF, PDF at 200 dpi.
- `evidence/ocr_step.py`: gate first; words into the sealed layer on a new `evidence_pages` row (`ocr-1`); publishes `evidence_text.ready`.
- `pages_of` prefers an OCR row for a page; every reader follows.
- `workflows.py` `patched("ocr")` between words and pii_scan.
- Replay: v8 history at the end pass.
- Rollback: flag `evidence.ocr` off; the page stays not_scannable.

## Progress log
- 2026-11-05: built. Tests at the S28 end review.

## Decisions made during this task
DEC-2309
