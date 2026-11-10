---
id: TASK-6716
title: "R-02-T24: parity and accessibility: Tier C for all 21 built artboards (locked), Tier D computed styles, axe on every scenario, forced colors, reduced motion, the keyboard path for pins, white-label crawler"
spec: SPEC-646
acceptance_criteria: [AC-37]
risk_zone: green
status: in-review
branch: s35-r02-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T24
---

## Objective
parity.json lists all 21 artboards at Tier C, axe reports zero serious or critical findings, and the crawler finds no 'Accrued' on any portal route.

## Plan
1. Gallery: POR-08, POR-09 and POR-15 registered with their scenarios and openings, `&w=390`
   for the phone (`portalArtboard`).
2. `docs/design/parity-manifest.json`: 21 Tier C `.window` entries, locked (POR-08 a, a2, b, c, d,
   e, e2, f; POR-09 a, a2, b, c, d, e, f; POR-15 a–f), sources pinned by SHA-256.
3. `e2e/screens/POR-r02-a11y.spec.ts`: axe at 1400 and 390 on all 21, forced colors, reduced
   motion, Tier D (T7 rail 336 · main 1030), the pin keyboard path (R-02-T22), and the crawler.

## Partial
- POR-09 g, h and i are not built (DV-06): not in the 21. Runs need Playwright browsers (CI).

## Progress log
- `2026-11-10` — Built; specs written, run in CI.
