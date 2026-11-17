---
id: TASK-8419
title: "C-01-T36: CLS-09 close plan editor"
spec: SPEC-655
acceptance_criteria: [AC-15, AC-17, AC-21, AC-22]
risk_zone: green
status: in-review
branch: c01-t36-cls09-plan-editor
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T36
---

## Objective
Spec section: docs/plan/epics/C-01.md §5 CLS-09. CLS-09 Close plan editor states a, a2, a3, b, b2, c, d, e and f on T6: version, Plan, Requests and History; By class and By procedure; O1 hover card; O2 row drawer pickers; draft diff 'Changed'; role-dependent Publish or Request publish; agent drafting card with outlined ticks until adopted; template cards and Draft from ledger history; history attribution.

## Plan (green)
1. `screens/CLS-09/{index.tsx,copy.ts,scenarios.ts,CLS-09.test.tsx}`: T6 control bar, tally strip from the version's `tally`, grouped plan table (class or procedure), hover card, O2 drawer with pickers on a draft (PATCH with If-Match), adopt ticks, Edit plan, Publish (confirm) or Request publish by `allowed_actions`, empty state with templates and Draft from ledger history, Requests and History tabs.
2. Fixtures: `seed/close-book.ts` thresholds per row, v4 draft (Raj/Priya), v1 agent draft, history, templates; `handlers/closes.ts` history and templates; `fixtures/scenarios/CLS-09.ts` a–f with `INITIAL`.
3. Route `/close-plans/$clientId` renders CLS-09; manifest status fixture.
4. Screen contract `docs/screens/CLS-09.md`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack. tsc, eslint and prettier clean on touched files; vitest not run yet (end pass). Partial (DV-a to DV-d in the screen contract): no AJE POLICY card or template tag (not in PlanVersionOut), template cards without description lines, drafting progress from the scenario, version stepper and Add procedure drawn without behaviour, ENG-03 monthly-close step UI not built. Lint: 'Accrual' (the procedure word) trips the product-name rule; one line-scoped disable with its reason (a rule that cannot tell the accounting word from a misspelt product name). Gates and tests run once at the S48 end pass (build first, test last).
