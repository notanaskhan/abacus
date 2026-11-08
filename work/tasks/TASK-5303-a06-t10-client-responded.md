---
id: TASK-5303
title: A-06-T10 notification on a recorded client decision
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # the row's notifications clause
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T10
branch: s25-a06-t10-notify
worktree: /Users/ayushkbhatia/Accrued/abacus-s25
created: 2026-11-06
updated: 2026-11-06
---

## Objective
A-06-T10's notifications: a recorded client decision tells the partner and managers.

## Plan (amber)
- `adjustments/decisions.py` emits `proposed_entry.client_decided`; `notifications/catalogue.py` maps
  it to `proposed_entry_client_responded` for the leads; `shell/notifications.ts` gets the words.
- Tests: `tests/integration/backfill/test_a06t10_client_responded.py`,
  `tests/unit/notifications/test_catalogue.py`.
- Rollback: revert. No migration.

## Progress log
- 2026-11-06: built. The client's own decision through the portal is R-02's; only record mode exists.

## Decisions made during this task
DEC-2422.
