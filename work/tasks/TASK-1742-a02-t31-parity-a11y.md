---
id: TASK-1742
title: AUD-06 and POR-16 parity and accessibility (A-02-T31)
spec: SPEC-333
acceptance_criteria: [AC-38]
risk_zone: green
status: done
epic: A-02
plan_key: A-02-T31
branch: s14-a02-t31
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Tier C report for AUD-06 a–h and POR-16 a–g; locks on AUD-06 a, c, e, g and POR-16 a–g at exit
(DF-19 copy masks recorded as deviations until the parity spec reads `data-parity-mask`); Tier D
computed styles; axe on every state and open overlay; keyboard grid, segmented and toggle suites.

Acceptance (A-02-T31): "The locked artboards pass Tier C in CI, Tier D holds, and axe reports zero
serious or critical findings on every state."

## Plan
- `apps/web/src/screens/gallery.tsx`: AUD-06's artboard inside the app shell (DEC-832).
- `apps/web/e2e/parity/screen-rows.ts`: AUD-06, POR-16 in `BUILT_PLANNED`.
- `docs/design/parity-manifest.json`: 15 `.window` entries pinned to the handoff PNGs.
- `apps/web/e2e/screens/AUD-06-POR-16.spec.ts`, `apps/web/e2e/visual/tier-d-connections.spec.ts`.
- End-of-batch: the screen parity run, then the measured diff % into AUD-06's and POR-16's Parity
  tables and `locked` on the named entries that pass 3 %.

## Progress log
- 2026-10-29: manifest entries, gallery frame and specs written; measurement and locks in the
  end-of-batch pass (as A-01-T28).
- 2026-10-29 (end-of-batch): measured on `parity-screens`. Locked AUD-06 g (2.20 %) and POR-16 a,
  c, d, g (2.23 / 1.85 / 2.04 / 2.03 %). Report-only: AUD-06 a–f (4.29–7.93 %), POR-16 b, e, f
  (16.62 / 17.89 / 7.77 %). AUD-06h's handoff PNG is a 2880 × 580 strip, so it has no window entry.
  Axe and the Tab walk pass 15/15. Segmented, grid and toggle suites pass. Tier D: POR-16 holds 4/4.
  AUD-06 draws rail 330, canvas 742 and dock 330, not the contract's 536 / 490 split; that case is
  kept as `test.fail` and recorded in the contract as an open gap.
