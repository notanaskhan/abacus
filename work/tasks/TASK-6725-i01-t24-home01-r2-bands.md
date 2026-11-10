---
id: TASK-6725
title: "I-01-T24: HOME-01 R2 To-dos and Mentions bands (h, i) as new unwired components"
spec: SPEC-650
acceptance_criteria: [AC-7, AC-29]
risk_zone: green
status: in-review
branch: s35-i01-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: I-01-T24
---

## Objective
Scenarios h and i render from data in /components/screens/HOME-01, Daniel's a2 fixture shows both bands empty with the header still 11, and the diff touches no file on HOME-01's live path.

## Plan
- `apps/web/src/components/screens/HOME-01/` (new; nothing under `screens/HOME-01/` changes, P-29 rule 2):
  - `copy.ts`: the R2 band copy, verbatim from revision.md.
  - `HomeBands.tsx`: `TodosBand` (C-30 rows: ring, title, from-person, object chip, due chip; opens SHL-17) and `MentionsBand` (AtSign chip, "<person> mentioned you", quoted text and object, time, unread dot; opens SHL-18). The bands use the built 31 px band and 44 px row grammar, on P-05's `TodoOut` and the C16 feed's `mention` items (read-time facts `actor_name`, `excerpt`, `object_label`).
  - `scenarios.ts`: a2 (Daniel, both empty, header 11), h (Hannah: 0 to-dos, the 12:35 PM unread and 8:31 AM read mentions), i (Marcus: SHL-17's row-6 to-do due Sep 16, 0 mentions). All of it is seeded data only.
  - `HomeBands.test.tsx`.
- Insights segment and Open Today slots: the live HOME-01 already carries `openToday`; the Insights segment behind its entitlement is not added (it would edit the live composition).

## Notes
- ACs: I-01 has no spec of its own; SPEC-650 (P-05) holds the bands' data (AC-7 HOME-01h, AC-29
  HOME-01i: the To-dos band reads the same query as My to-dos).
- DEC-61 (AC-7): the notification row never stores the comment body; the band's quoted text is a
  read-time fact the resolver opens for an authorised reader, never stored or emailed.
- The C16 mention row's facts (`excerpt`, `object_label`, `actor_name`) are what P-05-T06's resolver must answer; check at wiring (after Apr 20, 2028).

## Progress log
- 2026-11-10: built; tests at the end pass.
