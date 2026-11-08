---
id: TASK-6224
title: A-07-T22 close, the completion facts the projector lacked
spec: SPEC-644
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T22
branch: s31c-a07-t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (amber)
- `assurance/completion_facts.py` adds five providers:
  - `sign_offs` (AUD-17 matrix footer);
  - `sum` (the EP's `sum_conclusion` card);
  - `disclosure_checklist` (`reporting.api.checklist_counts`, new);
  - `form5500_tie` (EBP-07's draft);
  - `certification` (EBP-06's points).
- No migration. Rollback: unregister the five keys (they read "Not yet derived" again).
- Test `tests/unit/assurance/test_a07t22_more_facts.py`.

## Left
- `filing` is a person's item (the TPA files the Form 5500); `schedules` lands with TASK-6225.

## Progress log
- 2026-11-08: built; runs at the close end pass.
