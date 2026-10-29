---
id: TASK-2007
title: F-06-T08 TPL-01 Tax Returns practice board specimen
spec: SPEC-400
acceptance_criteria: [F2]
risk_zone: green
status: in-review
epic: F-06
plan_key: F-06-T08
branch: s15n-f06-t08
created: 2026-10-29
updated: 2026-10-29
---

## Objective
TPL-01 a–e on the T1 IndexList over the tax seed: eight registry tiles in TAX-01's order, split
filter chips, the Signature column with SignerChips, the due cell with its rule popover and Ext.
tag, days-to-due colouring from the demo clock, sync chips, Bulk actions, the season-start empty
state. Registered at `/components/screens/TPL-01?st=a…e`.

Acceptance: "TPL-01a reads 15 of 79 open sorted by extended due date, TPL-01b shows exactly the ten
returns behind E1-E10 with an amber Status chip, and synced chips never use a green-tint fill."

## Progress log
- 2026-10-29: built; `TPL01.test.tsx` written, not run (end review). tsc and eslint clean. The
  specimen computes the `counts` facet as the fixture server would; the template adds nothing up.
