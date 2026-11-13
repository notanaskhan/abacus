---
id: TASK-7931
title: I-02-T16 rest: HOME-01's compressed geometry beside the docked Today pane
plan_key: I-02-T16
spec: SPEC-654
acceptance_criteria: [AC-H1]
risk_zone: green
status: in-review
branch: i02-t16-docked-widths
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Finish I-02-T16's layout partial: with the Today pane docked, HOME-01 renders the handoff's compressed row (tiles 88, Audits 330, Closes 90, Notices 84) and a 380 right column, so the queue takes 506 of the 896 region.

## Done
- T11 kit: `DashTile` single and meter tiles take an optional `width` (120 and 160 stay the default); `DashboardLayout.columnWidth` (420 default) with a `data-dash-column` marker.
- HOME-01 `docked` passes the compressed widths; HOME-05 renders `<HOME01 docked />` beside the pane (collapsed stays HOME-01 exactly).
- Tests: tile widths and defaults; the right column 420 and 380.

## Partial
- Tier D pixel parity is I-02-T21 (S43).

## Progress log
- 2026-11-13: built in the S42 partials round; tests written, run at the partials end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
