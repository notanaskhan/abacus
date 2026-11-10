---
id: TASK-6222
title: A-05-T62 EBP modules runbook, README sections, skill notes, flag housekeeping
spec: SPEC-640
acceptance_criteria: [AC-1]  # a fresh session can flip, roll back and update EBP reference data from the runbook alone; every A-05 flag calendared
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T62
branch: s31-a05-t62
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-08
updated: 2026-11-08
---

## Plan
- `docs/runbooks/ebp-modules.md`, listed in the runbooks README. It covers:
  - what turns on what;
  - the per-firm flip order and rollback;
  - recording a correction;
  - recompute after an engine version change, through a checkpoint;
  - the annual IRC 6621, IRS limits and Schedule H updates with the CPA;
  - verification and the flag calendar.
- `assurance` and `workpapers` README sections; backend-module and frontend-feature skill notes.
- `docs/plan/status/flag-renewals-2027.md`: the three A-05 flags renewed before 2027-04-30 and
  retired after PW4.

## Partial
- The Schedule H mapping (`ebp_schedule_h_mappings`) has no import endpoint, so a real firm has
  no FS lines on EBP-07 until one exists. The runbook records this gap; the endpoint is a
  follow-up.

## Progress log
- 2026-11-08: written.
