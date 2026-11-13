---
id: TASK-7709
title: T-05-T46 Freeze tax-workbook v1 for T-07, T-06, T-04 and T-02
plan_key: T-05-T46
spec: SPEC-651
acceptance_criteria: [AC-F14]  # tax-workbook contract frozen; snapshot and stub route set pinned
risk_zone: amber
status: in-review
branch: t05-t46-workbook-freeze
worktree: /Users/ayushkbhatia/Accrued/abacus-s41
created: 2026-11-13
updated: 2026-11-13
---

## Objective
Final `docs/contracts/tax-workbook.md` and a frozen v1 snapshot so later epics build on fixed
shapes.

## Built
- §9 of the contract (cell store, grammar, run plan, schedules, allocation, K-1 drafts, routes
  still 501); README row frozen; snapshot `backend/tests/contracts/tax_workbook/v1.json` via
  `python -m abacus_tools.contracts --freeze tax_workbook v1`; `MODELS["tax_workbook"]`.
- The stub test's built set and route count follow S41.

## Partial
- The consumer contract tests of T-07, T-06, T-04 and T-02 are those epics' rows.
- Four routes were named by no later row. S41 leftovers (TASK-7733, DEC-4737): general
  information and partners are served; mappings was T-05-T37's; `PUT …/ownership` stays 501 (no
  version store, and its effect on an approved structure and the K-1 drafts is unplanned).
- TXP-11's tab titles stay the handoff's (deviation recorded in the contract).

## Progress log
- 2026-11-13: frozen; `contracts --check` passed locally (no output).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4712 | the freeze and the sheet-title deviation | no |
