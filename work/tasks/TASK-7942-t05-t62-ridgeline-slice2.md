---
id: TASK-7942
title: "T-05-T62: Brightwater Hale Ridgeline slice part 2 (memo adopted and approved, fix, Run 3, issue resolved, named snapshots)"
plan_key: T-05-T62
spec: SPEC-651  # T-05 §5.3
acceptance_criteria: [AC-F14]  # each named snapshot reproduces its artboards from the database; Sep 14 matches DF-34
risk_zone: amber
status: in-review
branch: t05-t62-ridgeline-slice2
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
The memo adopted Sep 10 and approved Sep 14 9:40 AM, the fix approved 9:51, Run 3 at 9:52
(TXP-00 B), the issue resolved and badge 10, memo stale; named snapshots Sep 8 10:02 AM, Sep 10
4:12 PM, Sep 14 9:24 AM and 9:52 AM.

## Plan (amber)
- `tax/memo_service.py` `record_synthetic_memo`; `tax/workbook_fix.py` `record_synthetic_fix`
  (both synthetic-only, 404 otherwise); exported with `memo_row`, `sign_memo` from `tax/api.py`.
- Scenario: `entity_memo.py` (TXP-01 text), `entity_slice.py` part-2 events and `FIX_ADDS`,
  `epochs.py` three named snapshots, `loader.py` four handlers.
- Tests: `backend/tests/unit/tax/test_t05t62_ridgeline_slice2.py`; the load at the end pass.
- Rollback: revert; the slice stays opt-in.

## Partial
- Carried from part 1: the LPA and assignment documents with word layers and the agreement
  reader's run are still not loaded (no word-layer seed for those documents).
- The 9:51 fix is recorded directly, not through a fix run's proposal and P-04 approval (the
  loader runs no Temporal workflow); the values, audit and checkpoint match `apply_fix`'s.

## Progress log
- 2026-11-14: built; events and imports smoke-checked; tests written, not run (S43 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4937 | memo and fix through synthetic-only recorders; real sign-offs; snapshots | no |
