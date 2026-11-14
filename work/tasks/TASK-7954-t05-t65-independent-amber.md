---
id: TASK-7954
title: "T-05-T65: independent AC tests (ADR-078) for AY's amber services part 2 (T-05-T32, T40, T42, T50, T51, T52, T54, T57, T61)"
plan_key: T-05-T65
spec: SPEC-651  # T-05 §3 F7–F11
acceptance_criteria: [AC-F7, AC-F8, AC-F9, AC-F10, AC-F11]
risk_zone: amber
status: in-review
branch: t05-t65-independent-amber
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Plan
- `backend/tests/unit/tax/test_t05t65_independent_amber.py` (ac-test-author notanaskhan; pure
  functions: queue counts and sections, fix parsing, memo staleness, reconciliation, export).

## Partial
- Import-mode parsing of hostile files (T-05-T40) and the fix flow's checkpoints (T50) need a
  database or files; they ride on T-05-T67's API journey (S44).

## Progress log
- 2026-11-14: written, not run (S43 end pass).
