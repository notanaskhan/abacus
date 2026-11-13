---
id: TASK-5311
title: A-05-T17 the cockpit rail's Version 1 child row; EBP-02's rail row live
spec: SPEC-640
acceptance_criteria: [AC-1]  # "Version 1 child row with diff ribbon"
risk_zone: amber
status: in-review
epic: A-05
plan_key: A-05-T17
branch: s25d-a05-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s25d
created: 2026-11-08
updated: 2026-11-08
---

## Objective
DV-EBP-02-5: the Version 1 child row in the cockpit rail opens the snapshot and its ribbon; retire
the header-pill workaround.

## Plan (amber: the cockpit projection every audit reads)
- `sections.SectionState.versions`, `SectionVersion`; `cockpit.SectionRow.versions`;
  `AuditSectionRowOut.versions` (additive); client regenerated.
- `ebp_designed`: EBP-02's provider lists earlier reviews; EBP-02 joins `LIVE`.
- Web: `rail.ts` children, `SectionRail` `onVersion`, `AuditCockpit` `onSectionVersion`, AUD-02 maps
  it to `?version=`; the pill is a label.
- Rollback: revert. No migration.

## Tests
`EBP-02.test.tsx` ("DV-EBP-02-5: the rail's Version 1 child row opens the earlier review"; the pill
test it replaces asserted the workaround this removes); `test_a05t16_plan_reads.py`.

## Progress log
- 2026-11-08: built. `tests/unit/identity/test_independence.py::test_ac7_visible_requires_a_confirmation_for_staff_roles`
  fails in this tree when run alone; this work's identity diff is one generated matrix entry, so it
  is not investigated here. The classification tests need `libgobject`, absent on this laptop.

## Decisions made during this task
DEC-2492.
