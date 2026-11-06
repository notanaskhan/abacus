---
id: TASK-3384
title: P-11-T25 key-value hints, re-scan and backfill, long scans
spec: SPEC-000  # row (P-11-T25)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: P-11
plan_key: P-11-T25
branch: s28p-p11-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-06
updated: 2026-11-06
---

## Objective
What DEC-2375 left unbuilt, as Ayush asked.

## Plan
- Hints in the sealed layer and `pii.detect_hinted`; `<detector>+ocr` and `<renderer>000` re-runs; `OcrBackfill` and `LongOcr`, patched `ocr_background`; histories. No migration.
- Rollback: revert before any firm has a re-scan row. After, the code must keep preferring them.

## Progress log
- 2026-11-06: built. `tests/integration/backfill/test_p11t25_ocr_run.py` (4), `tests/unit/evidence/test_p11t25_key_hints.py` (7), replay histories. See DEC-2383.

## Decisions made during this task
DEC-2383
