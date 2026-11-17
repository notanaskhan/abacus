---
id: TASK-8434
title: "A-08-T21: rest: an accepted entry puts the final analytics set out of date"
spec: SPEC-657
acceptance_criteria: [AC-5]
risk_zone: amber
status: in-review
branch: s48r-adjusted-out-of-date
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T21
---

## Objective
A-08-T21 named final-stage analytics on the C8 adjusted layer but left them Current when the adjusted layer moved. A client-accepted proposed entry now marks the work item's Current final-stage sets Out of date (adjustment_recorded) until a person runs them again.

## Plan (amber)
1. Subscribe analytics to proposed_entry.client_decided (accepted only); UPDATE the Current final sets to out_of_date with failure_code adjustment_recorded and audit analytics.went_out_of_date per set.
2. Integration test: a decline changes nothing, an accept stales the final set once, a replay writes nothing more.
3. No recompute by itself: a person reruns (AC-5.1 run is a person).

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5424). An accepted entry stales final sets; preliminary and substantive sets read the unadjusted layer and are untouched. `adjustment.approved` does not exist: the client acceptance is the event that puts an entry on the adjusted layer. Gates and tests run once at the S48 end pass (build first, test last).
