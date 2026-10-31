---
id: TASK-2224
title: I-01-T16 HOME-02 queue on T9 close-review; creates home.approvals
spec: SPEC-000  # I-01-T16 row and docs/screens/HOME-02.md
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: done
epic: I-01
plan_key: I-01-T16
branch: s17-i01-t16
created: 2026-10-30
updated: 2026-11-01
---

## Objective
HOME-02 queue on T9 close-review: subbar Approvals and viewer name, segmented, Sort chip and
Select, Waiting on you header with Show done, 49h bands with counts and chevrons, 50–72h rows with
glyphs and due sub-lines in risk words, selection state, J/K and Enter, `?gate=` deep link, empty
state f; creates flag `home.approvals`.

Acceptance (backlog row): "Scenarios a and f pass Vitest and axe, J/K moves the selection with
focus announced, and the band counts equal the HOME-01 badge."

## Plan
- Flag `home.approvals` (`feature-flags/practice.yaml`, regenerated `kernel/_flags.py`).
- `packages/ui`: IssueItem `glyph` (additive); QueueDetailLayout `bare` (routed, no second toolbar).
- `screens/HOME-02/{index.tsx, copy.ts, scenarios.ts, HOME-02.test.tsx}`; fixtures HOME-02 turn the
  flag on; route `/home/approvals` with `?gate=` (UUID only); manifest `fixture`; gallery entry.
- Detail, evidence and bulk Select are I-01-T17/T18/T19 (Select drawn disabled only where planned).

## Progress log
- 2026-10-30: built in S17 Lane 2 off main; tests run in the end review.
- 2026-11-01: merged to main in #796 (52978b13b).
