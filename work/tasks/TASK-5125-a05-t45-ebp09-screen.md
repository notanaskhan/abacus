---
id: TASK-5125
title: A-05-T45 EBP-09 grid, compliance and qualification tabs, a to e
spec: SPEC-000  # row (A-05-T45)
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-05
plan_key: A-05-T45
branch: s29-a05-t45
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
EBP-09 on T6 in the AUD-02 cockpit: spreadsheet grid with cited cell and Sheet!Cell footer, three tabs with scoped tallies, exception variant d as a fixture.

## Plan
screens/EBP-09; fixtures/seed/ebp09, scenarios/EBP-09; AUD-02 composes it under ebp_09. Backend additive: provider_name, disclosure_text, citation_labels on ExpenseRowOut.

## Progress log
- 2026-11-06: built. `apps/web/src/screens/EBP-09/EBP-09.test.tsx` written, not run (end pass). tsc and eslint clean.

## Decisions made during this task
DEC-2421
