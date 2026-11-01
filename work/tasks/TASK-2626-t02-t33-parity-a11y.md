---
id: TASK-2626
title: T-02-T33 parity and accessibility for T-02's six screens
spec: SPEC-502
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
epic: T-02
plan_key: T-02-T33
branch: s21-t02-t33
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"parity.json is published with the locked frames passing and axe reports zero serious or critical
findings." (T-02 §5.4, §5.5.)

## Scope
- `docs/design/parity-manifest.json`: 43 Tier C window rows (TAX-01 a–g, TAX-02 a–f, TAX-03 7,
  TXP-12 11, POR-05 6, POR-13 6), the 19 §5.4 frames locked (DEC-1671).
- `apps/web/e2e/visual/tier-d-t02.spec.ts`: toolbar 46, record header 42, tabsbar 44, pane header
  46 on the T1/T2 hosts; the portal toolbar 46 on T7; Tab through TAX-01's tiles; Enter opens and
  closes TXP-12's and POR-05's expandable rows; POR-05's Saved time in a polite live region.
- `apps/web/src/screens/POR-05/index.tsx`: the Saved time gains `aria-live="polite"`.
- Axe on every scenario at 1400 and 390 is T-02-T32's `t02-screens-widths.spec.ts`.
**Not here**: O3 sheet and Undo-toast keyboard paths are the kit's (C-series specimens' suites).

## Progress log
- 2026-11-01: written; runs at the batch's end review.
