---
id: TASK-1218
title: ENG-02 "On hold with reason" control (carried from P-07-T28) and ED-027's decision (DEC-343)
spec: SPEC-321
acceptance_criteria: []
risk_zone: green
status: done
epic: P-07
plan_key: P-07-T28
branch: s8b-eng-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
ENG-02's status pill ⌄ menu: Active / "On hold…" with a reason code, over DEC-328's hold and resume routes. The rest of P-07-T28 stays as built (the Activity tab waits for C-01). Also record Ayush's ED-027 decision (2026-10-25) as DEC-343: ENG-01's "Period │ Current" excludes archived engagements.

## Progress log
- 2026-10-25: DEC-343 recorded; ENG-01 contract figures amended (273, Archived 0; 275 is Period │ All); the ED-027 strict xfail replaced by a test of the decided behaviour; fixture handler and ENG-01 tests follow; ED-027 fixed.
- 2026-10-25: hold control built (DEC-344): `EngagementRecordOut.hold_reason` and `engagement.hold` in the record's actions (contract first, `make regenerate`), the menu, the reason dialog, resume, fixture hold/resume handlers, three ENG-02 tests and one integration test.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-343 | ED-027: spec and DEC-224 disagreed on Period │ Current | No |
| DEC-344 | The hold dialog, reason words and toasts are undesigned | No |
