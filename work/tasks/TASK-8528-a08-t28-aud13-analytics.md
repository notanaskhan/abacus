---
id: TASK-8528
title: "A-08-T28: AUD-13 analytics screen states a-e plus Substantive"
spec: SPEC-657
acceptance_criteria: [AC-5]
risk_zone: green
status: in-review
branch: a08-t28-aud13
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T28
---

## Objective
AUD-13 states a-e plus the Substantive tab on the T6 grammar inside T2 in fixture mode: tally strip, segmented stages, threshold tooltip naming the deciding partner, run rows, Ask client sheet with editable templated cards, answered chip with Accept, final layer. AC: tallies foot 14 = 8 + 6 and 8 = 6 + 2, unexplained rows amber, no dollar sign in the table.

## Plan (green)
1. fixtures/seed/fieldwork.ts: explanations, unexplained notes, client questions and answer, runs, the three AJEs, final lines and explanations, subtotals, verbatim from the handoff canvas #aud13
2. screens/AUD-13: scenarios (a-e, s), copy, index (AnalyticsWorkspace: statement table with groups and subtotals, TallyStrip, RunRows, AskClientSheet on SheetModal), AUD-13.test.tsx
3. screens/kit-a08-data.ts re-exports the seed (screen import rule); gallery registers AUD-13

## Progress log
- `2026-11-17` — Built; AUD-13 vitest 14 pass, tsc and eslint clean. Live swap (route /audits/$auditId/analytics on the generated client) is A-08-T32. Gates and tests run once at the S49 end pass (build first, test last).
