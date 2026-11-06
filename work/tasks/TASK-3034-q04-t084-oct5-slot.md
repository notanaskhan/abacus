---
id: TASK-3034
title: Q-04-T084 Tuesday slot Oct 5, rehearsed on the synthetic test firm
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # the release record shows window_mode and rollback, and every flip has both approvals
risk_zone: red
status: done
epic: Q-04
plan_key: Q-04-T084
branch: s25-q04-t084
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"The release record shows window_mode and rollback, and every flip has both approvals." Run on
PF-X1 and reported as synthetic (DEC-1530, DEC-2081): no pilot firm is live and no production
stack exists.

## Plan (red)
- `backend/src/abacus_tools/window_rehearsal.py` (new): the real P-29 gate at chosen instants,
  with a synthetic firm treated as live in memory only; rehearsal records carry zero digests.
- `docs/ops/windows/2027-10-05-tuesday-slot.md`: the slot's readings, the migrate time, the flips.
- Tests: `tests/unit/tools/test_q04t084_window_rehearsal.py` (also covers T085's week).
- Rollback: revert. `deploy/windows.yaml` is unchanged; no migration, no flag.

## Open / needs a live firm
A real release record and its closing note; RB-16 §6's staging, shadow and canary checks; both
founders' approvals on an actual flip.

## Progress log
- 2026-11-03: built; rehearsal tests 11 passed.

## Decisions made during this task
DEC-2081.
