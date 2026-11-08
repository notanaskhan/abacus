---
id: TASK-6207
title: A-07-T23 subsequent events, legal letters, going concern and the bring-down
spec: SPEC-000  # A-07 F2 (docs/plan/epics/A-07.md)
acceptance_criteria: [AC-1]  # fires 9:00 AM CDT Oct 9 2026, re-arms, never concludes
risk_zone: amber
status: in-review
epic: A-07
plan_key: A-07-T23
branch: s31-a07-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan (amber)
- `assurance/subsequent_events.py`: procedures (add, perform as a person), events (sealed,
  human-only), legal letter N/A with a sealed basis or a P-06 request item, going-concern inputs
  computed by code (DSCR, covenant, headroom; engine version and inputs hash) and the EP's
  `going_concern` card raised through `review.api`.
- `assurance/bring_down.py`: `BringDownWorkflow` (durable timer to 09:00 firm time on the report
  date as a UTC instant; `report_date_changed` re-arms), activity `assurance.bring_down` (counts
  procedures through the report date, asks each team member to reconfirm independence, records
  `bring_down.completed`; no conclusion), `schedule_bring_down` via `signal_with_start`, only
  when A-07 is live (COMPLETION_LIVE and in_app).
- Registered on the background class; recorder `record_bring_down`; replay test.
- Tests: `tests/workflows/test_a07t23_bring_down_timer.py` (time-skipping),
  `tests/workflows/test_a07t23_bring_down_replay.py`, `tests/unit/assurance/test_a07t23_going_concern.py`.

## Partial
- The replay history is recorded at the end pass (needs the local Temporal stack).
- Nothing calls `schedule_bring_down` yet: A-07-T27's report record sets the report date and calls
  it. The dock's run #4240 RunCard is AUD-19's fixture (A-07-T25); the activity opens no agent run.
- The routes stay 501 until A-07-T33.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-2807 | Fire times outside the workflow; reconfirmation as events; inputs code-computed | no |
