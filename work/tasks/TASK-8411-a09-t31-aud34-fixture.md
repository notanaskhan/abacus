---
id: TASK-8411
title: "A-09-T31: AUD-34 Group scoping a-f in fixture mode"
spec: SPEC-658
acceptance_criteria: [AC-5]
risk_zone: green
status: in-review
branch: a09-t31-aud34-fixture
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T31
---

## Objective
Spec section: docs/plan/epics/A-09.md §3.5 (AUD-34). Group scoping a-f in fixture mode: T2 cockpit with T6 grammar, SHL-11 DecisionCard (rationale required, reserved to the EP, manager banner and Remind Margaret), Components, Coverage and Aggregation segmented, planned-work picker with the agent suggestion, coverage bars with table, citation chips, Draft component instructions footer, flag-off f.

## Plan (green)
1. `screens/AUD-34/`: `copy.ts` (every word and figure verbatim from the handoff, the five components), `scenarios.ts` (a to f with persona and clock as the handoff), `index.tsx` (`GroupScoping`: header and pill, segmented control, tally strip, SHL-11 decision card with RadioGroup and the required rationale, the manager banner and Remind Margaret, the decided one-line, the components table with pending PM tooltips, the planned-work suggestion on Real Estate in d, coverage bars, aggregation, Draft component instructions… once decided, FlagOffState in f), gallery registration.
2. Tests: `screens/AUD-34/AUD-34.test.tsx` (each artboard, manager radios disabled with the banner, Decide disabled without a rationale, never 83%, PMs below group PM and none for Operating Co., Draft instructions only when decided).

## Progress log
- `2026-11-17` — Built in the S48 sequential stack. tsc and eslint clean. Partial: the screen is fixture mode as the row asks (its live swap is A-09's later row); the planned-work Picker is drawn as the suggestion line, not an open popover; Tier C parity runs at the end pass. Gates and tests run once at the S48 end pass (build first, test last).
