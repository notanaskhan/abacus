---
id: TASK-6006
title: "A-06-T32 golden-figure seed tests: one figure book, the scenario and the fixtures"
spec: SPEC-000  # row (A-06-T32)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-06
plan_key: A-06-T32
branch: s29l-a06-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
The seed tests fail on any figure drift between the scenario, fixtures and screens.

## Plan
backend/tests/golden/scenario/brightwater_hale/completion_figures.json: the row's figures transcribed from A-06 §2 (AUD-15 bands and total, the SUM, net assets, the tie-out, the checklist, review notes, the matrix and its footer). Backend test_a06t32_completion_figures.py checks the Brightwater Hale completion slice (findings by severity, the declined entries' rollover and iron curtain, PM against the materiality goldens, net assets against the EBP goldens, the checklist and notes counts). Web fixtures/contracts/completion-figures.test.ts checks the AUD-15, AUD-16, AUD-17 and AUD-20 fixtures (bands through AUD-15's own bandOf, the SUM, tie-out and checklist, notes and the matrix footer) against the same book. The 26-row matrix fails strictly on both sides (DEC-2391).

## Progress log
- 2026-11-07: built. Backend 7 passed, 1 strict xfail; web 4 passed, 1 expected fail. AUD-15's tab badge of 3 has no fixture field, so it isn't asserted.

## Decisions made during this task
DEC-2606
