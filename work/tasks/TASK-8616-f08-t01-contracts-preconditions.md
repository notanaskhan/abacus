---
id: TASK-8616
title: "F-08-T01: Screen contracts and precondition check for T18–T22 and TPL-20–24"
spec: SPEC-000
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: f08-t01-contracts-preconditions
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: F-08-T01
---

## Objective
Spec section: docs/plan/epics/F-08.md §0, §2. Ten screen contracts (74 artboards) with persona, clock, parity tier, footing, AVOID and deviations; record P-59, P-15, P-07, P-35, P-42, P-28 state on main, DEC-95 decided with P-20 proposed, P-25 not accepted.

## Plan (green)
1. docs/plan/status/F-08-preconditions.md: the gate table with the F-08 tasks each gates.
2. Ten contracts generated from the handoff READMEs with F-08 §2 deviations and AVOID lists.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5616). Docs only. Found: P-59 (TipTap) not drafted and P-15 (ADR-232) proposed; neither gates an S50 row (T20 is S54, T13 S52). Gates and tests run once at the S50 end pass (build first, test last).
