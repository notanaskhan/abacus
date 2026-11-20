---
id: TASK-8755
title: "C-01-T50: Parity and accessibility: Tier C report for every built artboard with the locks listed in section 10; Tier D close geometry blocking; axe on every scenario and open overlay; keyboard suites; reduced motion"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s51-c01t50
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-01-T50
---

## Objective
axe reports 0 serious or critical findings, Tier D passes, and the locked artboards stay within Tier C tolerance.

## Plan (green)
1. Screen specs `e2e/screens/CLS-01…06, CLS-09, CLS-10.spec.ts` on a shared `close-boards.ts`: every scenario on its live route in fixture mode (ids resolved by screen-scenarios), motion reduced, nothing busy (CLS-01 e is the designed loading state), axe at zero serious or critical in light and in forced colors, overlays included.
2. `e2e/screens/POR-11.spec.ts`: a–c at 1400 and a at 390 from the gallery, axe in light and forced colors, and no firm-only word on the client's page.
3. Fix what axe found: Radix menu triggers on <span> (aria-allowed-attr) in CLS-02's status pill and run history and CLS-09's version stepper become buttons; ink-4 on readable text (CLS-02's 'Started … ago' and composer placeholder) goes to ink-3; Amount draws an explicit zero ($0.00) at ink-3, keeping ink-4 for the zero dash (DEC-5745).
4. Parity tables lock CLS-01 a, b, c, e, CLS-09 a, e, f and CLS-10 a, d at Tier C per C-01 §5.4, with host Tier D rows.
5. Rollback: revert the PR.

## Progress log
- `2026-11-20` — Built, stacked on #2393. Ran locally on this worktree's own port: 64 close screen tests pass (light and forced colors) after the fixes; before them 29 failed (Radix span triggers on CLS-02 and CLS-09; ink-4 contrast on CLS-04's and CLS-05's $0.00 balances and CLS-02 text; CLS-01 e's designed busy state). packages/ui components 338 and close screen unit tests pass except CLS-02 'renders Deliverables (CLS-08, C-02's) disabled', which fails on the base too (CLS-08 shipped in C-02-T23, so the tab is live): left as is and reported. Not done: Tier C diffs and Tier D measurement (handoff baselines absent); CLS-02…06 and POR-11 have no docs/screens contract, so their §5.4 locks can't be written into a Parity table yet; the §5.5 keyboard suites beyond axe (tree, MatchProvider, segmented, drawers) are not written. Gates and tests run once at the S51 end pass (build first, test last).
