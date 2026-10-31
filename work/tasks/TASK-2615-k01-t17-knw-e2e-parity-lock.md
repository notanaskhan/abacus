---
id: TASK-2615
title: K-01-T17 KNW-03 program editor e2e, J01 step 6 on KNW-03 c, KNW-01 and KNW-03 parity lock
spec: SPEC-000  # K-01 §3.4, §3.5 and §5.5
acceptance_criteria: [AC4.1, AC4.2, AC5.1]
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T17
branch: s21-k01-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"The specs pass in both modes and parity.json shows KNW-01a-f and KNW-03a-f locked at Tier C by
Fri Aug 20, 2027." (K-01 §5.5, §10.)

## Scope
**In**: `apps/web/e2e/journeys/knw-03-program-editor.spec.ts` (a: a citation lands on step 4 lit,
"16 steps · 8 mandatory"; b: the SHL-07 popover names BH-EBP-110 and counts 1 citation; c: Hannah's
Draft v4 with + Step, mandatory steps locked to the QM owner and their trash disabled; Open in
Excel downloads the version; no Publish or Approve anywhere, INV-1), J01 step 6 extended to KNW-03 c,
and twelve parity-manifest entries `KNW-01{a-f}.window` and `KNW-03{a-f}.window` at Tier C,
`locked`, pinned to the handoff PNGs' SHA-256. Axe and INV-1 to INV-5 run after every step
(harness).
**Deviations (DEC-1663)**: the spec lives under `e2e/journeys/` beside `knw-01-catalog.spec.ts`,
not `e2e/knowledge/` (the harness projects pick up journeys only); fixture mode opens KNW-03's
gallery artboards (`/components/screens/KNW-03?st=`) rather than reaching into `src` for fixture
ids (lint `no-restricted-imports`). Full stack and staging stay `test.fixme` until the demo firm
has the methodology slice and `methodology.programs` (as KNW-01's spec); "both modes" is met on the
fixture project now and on full stack when E0 carries the slice.

## Progress log
- 2026-10-31: built; the specs and the parity sweep run at the batch's end review.
