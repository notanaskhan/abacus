---
id: TASK-1742
title: AUD-06 and POR-16 parity and accessibility (A-02-T31)
spec: SPEC-333
acceptance_criteria: [AC-38]
risk_zone: green
status: in-review
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
