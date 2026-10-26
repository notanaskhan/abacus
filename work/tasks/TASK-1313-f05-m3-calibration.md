---
id: TASK-1313
title: F-05 M3 calibration - kit-task throughput for S1 and S2, hold or cut (F-05-T26)
spec: SPEC-045
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: F-05
plan_key: F-05-T26
branch: s10-f05-t26-kit-throughput
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Kit-task throughput for S1 and S2 in the capacity ledger with a recorded hold or cut decision,
and the post-rebalance S1–S6 plan for F-02…F-05 beside the measured figures.

## Plan
- Measure from the read-only reconcile of main (`reconcile-S0-S9-2026-10-26`), not task-file
  statuses: F-05 S1 and S2 rows planned versus fully built.
- `docs/product/capacity-ledger.md` F-05 section: the throughput table, the decision, and F-05 §9's
  rebalanced plan beside delivered figures for F-02…F-05.
- DEC-410 records hold, no cut. No code. Rollback: revert.

## Progress log
- 2026-10-26: measured 86% (16.0 of 18.5); hold. Written (build-first; checks at the end).
