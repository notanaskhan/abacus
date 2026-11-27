---
id: TASK-9029
title: "K-03-T23: SHT-02 column drawer (?ov=column:new|<id>)"
spec: SPEC-721
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-k03-t23-column-drawer
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: K-03-T23
---

## Objective
SHT-02 a-f: the O2 480 column drawer over SHT-01 with the 11-type picker, date range, Required, classification with reason, Used in, type-change warning, blocked delete and the not-a-manager suggest path; template mode for KNW-06.

## Done
- SHT-02a-f render with exactly the 11 types in order
- Restricted is the default for client-data columns, a lower level needs a reason
- Save disabled until a change
- Suggest to Hannah Leclerc prefills an SHL-18 mention
- sheet and sheet_row comment anchors registered (Postgres test)
- Fixture from the Python scenario (scenario.sht02-column.json)

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6034 on the SH-1 stub (the columns service is K-03-T24). Found while building: collaboration had no sheet or sheet_row anchor, so K-03-T22's Comments tab would have failed live. Fixed here with sheet_anchor.py and tested on Postgres. 9 SHT-02 tests and 130 web files green. Contract and sh1 tests and the activity catalogue green.
