---
id: TASK-5309
title: A-05-T17 the viewer's matching line lights on hover and pin; c opens the SPD on p. 6
spec: SPEC-640
acceptance_criteria: [AC-1]  # "Hovering a provision lights the same line in the viewer"
risk_zone: green
status: done
epic: A-05
plan_key: A-05-T17
branch: s25d-a05-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s25d
created: 2026-11-08
updated: 2026-11-08
---

## Objective
DV-EBP-02-3: the row's acceptance. Hovering a provision lights its line in the viewer; c's row opens
the SPD on p. 6 with the line lit.

## Plan
- `ebp_provisions._spot` and `ProvisionOut.source_match`; client regenerated.
- `DockViewer` `shared` (no own scope; `scrollToLit`); AUD-02 passes it while Plan Review is open.
- EBP-02 rows: store intent on hover, pin and dock on click.
- Fixtures: the adoption agreement and SPD in the trust seed with their lit lines.
- Rollback: revert. No migration.

## Tests
`apps/web/src/screens/EBP-02/EBP-02.test.tsx` (click, hover, c), `test_a05t16_plan_reads.py` (`_spot`).

## Progress log
- 2026-11-08: built.

## Decisions made during this task
DEC-2490.
