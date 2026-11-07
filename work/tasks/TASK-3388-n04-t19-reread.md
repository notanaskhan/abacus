---
id: TASK-3388
title: N-04-T19 the responder reads again once a person names the taxpayer
spec: SPEC-000  # row (N-04-T19)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T19
branch: s28q-n04-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s28
created: 2026-11-07
updated: 2026-11-07
---

## Objective
For a real firm the responder's reading of a notice no form map covers was always refused: `DataSubject(None, None)` fails the §7216 gate closed, so the agent path only ever ran for synthetic firms. Read again once a person has named the taxpayer and the year.

## Plan
`revise` emits `notice_intake.taxpayer_named` when it leaves a `no_map` manual-entry intake with a client and a year; the subscriber dispatches `NoticeIntakeRereadWorkflow` (interactive, one activity); `reread_named` calls the responder with the real subject. History, replay, worker pin, Postgres tests.

## Progress log
- 2026-11-07: built. 83 targeted passed (the N-04-T19 file with 3 new tests, replay, worker screening, sandbox). Gates at the end of the round.

## Decisions made during this task
DEC-2387
