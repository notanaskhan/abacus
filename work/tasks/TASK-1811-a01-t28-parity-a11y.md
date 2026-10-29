---
id: TASK-1811
title: AUD-01/02/03 parity and accessibility (A-01-T28)
spec: SPEC-330
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T28
branch: s13r-a01-t28
created: 2026-10-28
updated: 2026-10-28
---

## Objective
22 artboards at Tier C (AUD-01 a–h, AUD-02 a–g, AUD-03 a–g; AUD-02 f report-only), locks on AUD-01 a–f, AUD-02 b and g, AUD-03 a–g; Tier D on the T1 and T2 hosts; keyboard and axe on every artboard.

## Plan
- `docs/design/parity-manifest.json`: 22 `aud-0Nx.window` entries, each pinned to its handoff PNG's SHA-256 (Tier C).
- `apps/web/e2e/screens/AUD.spec.ts`: render, axe zero serious/critical, Tab reaches a control with a ring, per artboard.
- `apps/web/e2e/visual/tier-d-audits.spec.ts`: host geometry from the contracts.
- End-of-batch: `pnpm visual:baselines`, the screen parity run, then write the measured diff % into the three contracts' Parity tables and set `locked` on the entries that pass 3 % (AUD-02 f report-only; AUD-02 a, c, d, e report-only with the dock masked until P-09).

## Progress log
- 2026-10-28: manifest entries and specs written; measurement and locks in the end-of-batch pass.

- 2026-10-29 (review): measured on `parity-screens` (AUD added to `BUILT_PLANNED`, as POR-03/04/14/20: the registry keeps them planned for DEC-195). AUD-01 a, b, c, e, f pass 3 % and are locked in the manifest; AUD-01 d (3.01), AUD-02 (2.40 to 7.63) and AUD-03 (3.25 to 12.66) stay report-only, diffs written into each contract's Parity table. The parity report has no masks, so the dock, spinner and viewer masks the contracts name are not applied yet. Axe and keyboard walk 22/22, Tier D hosts 3/3 (AUD-01 uses IndexList's `data-list="tabs"` and the section header, not the shell's tabsbar and PaneHeader).

- 2026-10-29 (masks): the parity harness takes a manifest `mask` (CSS selectors inside the shot). Both runners (`parity-screens` and `visual`) measure each selector's box on the render and paint it #ff00ff on the shot and on a copy of the handoff baseline (`<name>.masked.png`, written beside it under the ignored `.visual/`), then compare those. Playwright's own `mask` paints only the actual image, which against a handoff PNG adds diff instead of removing it. `crop_handoff.parse_entry` validates the field. Masked: AUD-01d's processing spinner, AUD-02 a–g's dock. Re-measured: AUD-01d 3.01 to 3.005 (240 px over), AUD-02 a–g 3.84 to 6.43 (d 1.34). Nothing new locks. The rest is layout (AUD-01d's row order, AUD-02's header and list about 14 px low), screen work rather than masking; contracts updated.
