---
id: TASK-2225
title: K-01-T13 KNW-03 program editor a, b, e on T2 RecordCockpit
spec: SPEC-000  # K-01 §3.4 AC4.1–AC4.3; KNW-03 handoff and R2
acceptance_criteria: [AC4.1, AC4.2, AC4.3]
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T13
branch: s17-k01-t13
created: 2026-10-30
updated: 2026-10-30
---

## Objective
KNW-03 on the T2 RecordCockpit: record bar, rail overview and programs, steps table with Rules and
Skill columns, Segmented Steps / Guidance / PBC links / Rules / Change log, Guidance dock with
where cited from C4, arrival with `?step` and `from=citation` (a), SHL-07 popover (b), Change log
(e), Open in Excel.

Acceptance (backlog row): "KNW-03a, b and e pass Tier C, step 4 is lit on arrival from an AUD-04
citation, and every BH-EBP-110 row reads a dash in Rules and Skill."

## Plan
- Fixtures: `seed/knw03.ts` (16 steps verbatim, v2 stand-ins for 7, 9, 10; PBC rows; guidance),
  `handlers/knw03.ts` (program, version, programs, steps, resolve, citations, export),
  `scenarios/KNW-03.ts` (a, b, e).
- Screen `screens/KNW-03/{index.tsx, copy.ts, scenarios.ts, KNW-03.test.tsx}`; Change log computed
  by `changesOf` (stable step keys); route `/knowledge/programs/$programId` behind
  `methodology.programs` with `?segment`, `?step`, `?from=citation`; manifest path; gallery.

## Progress log
- 2026-10-30: built in S17 Lane 2 off main; tests and Tier C run in the end review.
