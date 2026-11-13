---
id: TASK-7928
title: W-02-T15 rest: the v2 session's side-queue replay history
plan_key: W-02-T15
spec: SPEC-653
acceptance_criteria: [AC-L6]
risk_zone: amber
status: in-review
branch: w02-t15-side-queue-history
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish W-02-T15's replay partial (ADR-090): record the v2 session's side-queue shape (a question open while a second message is answered).

## Done
- `record_s42_runs` records `workbench-session-v2-side-queue.json` (Docker, stubbed activities); `test_s42_runs_replay.py` replays it with the other v2 histories.
- Compaction and the plans gate are inside the turn activity: with plans off a turn answers like the read-only one (no child), and compaction changes the activity's input only, so both replay as the recorded read-only and child-run shapes (DEC-4924).

## Partial
- None.

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4924 No separate compaction or plans-gate history | They change the turn activity's input or result, not the workflow's commands | no |
