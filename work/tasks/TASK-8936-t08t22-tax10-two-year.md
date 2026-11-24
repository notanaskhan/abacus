---
id: TASK-8936
title: "T-08-T22: TAX-10 two-year comparison a-e"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s53-t08t22
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T22
---

## Objective
TAX-10 a-e on T6 inside the ReturnFrame: SheetTabs sub-navigation, tally strip, All lines/Over threshold, statement table with amber, accepted and explaining cells, Accept and inline Edit, citation chips to SHL-08, threshold popover, line links to TAX-05, Open in Excel. Acceptance: TAX-10 a-e render from data, Accept is offered only to the reviewer, and the agents-off state lets Samuel Ito type an explanation.

## Done
- Additive line_ref/group/total (line map LINE_GROUPS/REFS/TOTALS) and explaining/explain_unavailable_reason on the live two-year read
- Python two_year_slice (a-e, x1) exported as scenario.tax10.json, every delta by code
- screens/TAX-10: sub-navigation, filter, threshold popover, Open in Excel, tally, statement grammar, explanation cells (accepted/proposed/unexplained/explaining/agents-off), Accept/Edit/Explain
- Route review/two-year behind tax.two_year; TAX-02 link live; manifest fixture; registry + e2e spec
- TAX-04 frame route-list test updated for T-06-T45's workpapers route
- Tests: TAX-10 9, slice 3

## Progress log
- `2026-11-23` — 2026-11-23: built in the S53 sequential run; targeted tests pass; integration/e2e in the end pass.
