---
id: TASK-2623
title: T-01-T52 parity and accessibility for CLI-05, ADM-05, ADM-08, TAX-09 and TAX-12
spec: SPEC-501
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: T-01
plan_key: T-01-T52
branch: s21-t01-t52
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"parity.json has a row for every artboard with Tier D passing, and axe reports zero serious or
critical findings." (T-01 §5.5, §5.6.)

## Scope
- Parity manifest: 36 rows, every artboard of the five screens at Tier C (CLI-05 a–g, ADM-05 a–h,
  ADM-08 a–g, TAX-09 a, a2, b–e, d2, TAX-12 a, a2, b, c, c2, d, e), TAX-09 and TAX-12 locked,
  each pinned to its handoff PNG's SHA-256.
- Tier D (`e2e/visual/tier-d-tax.spec.ts`, blocking): TAX-12's rail 330, canvas header 46, signer
  rows 52 and packet rows 36; TAX-09's popover 462; CLI-05's rail 330; Tab through TAX-12's rail;
  no running animation under reduced motion.
- TAX-09's sync chip state is announced in a polite live region (T-01 §5.6).
- axe on every scenario: the five screen specs of T-01-T46 (stacked on #1003).
**Deviation (DEC-1670)**: TAX-09, TAX-12 and ADM-08's artboards draw the screen without the app
shell, so their window crops are compared report-only at Tier C with that reason; the lock is
recorded and blocks once the artboards are framed. Forced colors run in the journey harness's
first axe step; keyboard suites for the diff sheet checkboxes, the confirm dialog and the selection
bar beyond the rail are left to the screen tests already on main.

## Progress log
- 2026-11-01: written; parity and Tier D run at the batch's end review (visual project).
