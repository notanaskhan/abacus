---
id: TASK-379
title: S1-S2 decision burn-down and ADR backlog close-out (F-02-T12)
spec: SPEC-000
acceptance_criteria: [AC-21]
risk_zone: green
status: done
epic: F-02
plan_key: F-02-T12
branch: f02-t12-burndown
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"By Fri Nov 27 every DEC row due by S2 is decided, defaulted or re-dated with an owner, and
backlog.md shows each S0-S2 ADR accepted or re-dated."

## What changed
- `docs/product/decision-log.md`: the 38 open rows due by 2026-11-27 (DEC-24 to DEC-78) are
  decided with the plan's proposed option (AGENTS.md "How you work" 2; AMENDMENT-solo). Rows
  already built point at their artefact (DEC-30, 39, 43, 47, 62, 71, 74). Counsel's part of
  DEC-25, 52, 71 and 72 is owned by ayushkbhatia by the row's original date.
- DEC-20, DEC-46, DEC-64, DEC-65 and DEC-70 were already decided.
- `docs/adr/backlog.md`: 25 S0-S2 ADRs still to draft are re-dated to their epic's first task,
  owner ayushkbhatia. P-26 and P-29 stay proposed with ayushkbhatia as the accepting decider;
  red ADRs never default on silence, so none is marked accepted here.
- 20 rows due after S2 (DEC-80 onward) stay open on their dates.

## Progress log
- 2026-10-22: done in one session.
