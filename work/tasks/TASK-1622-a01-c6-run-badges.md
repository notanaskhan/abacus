---
id: TASK-1622
title: C6 v1 swap for the Processing pill, popover and audit-bar run time (A-01-T27)
spec: SPEC-314
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T27
branch: s13-a01-t27
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Light AUD-01's Processing pill and AUD-02's run time from C6 v1 engagement runs, never from policy ticks.

## Plan
- `agents/engagement_runs.py` (`active_engagement_runs`, `register_engagement_run_agent`), exported by `agents.api`; `assurance/run_badges.py` registered with `register_run_summary`.
- The front end already renders `AuditRunBadgeOut` for fixture d and live data alike (no change needed).
- This branch merges origin/main (C6 v1 run summary, #510).
- Test `tests/unit/assurance/test_a01t27_run_badges.py`. DEC-717.
- Left open: the Pilot 0 top-10 fixes (the F-09-T93 list does not exist yet).

## Progress log
- 2026-10-28: built.
