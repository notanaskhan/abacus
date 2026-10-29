---
id: TASK-1811
title: AUD-01/02/03 parity and accessibility (A-01-T28)
spec: SPEC-330
acceptance_criteria: [AC-1]
risk_zone: green
status: done
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

- 2026-10-29 (layout): the residue was mostly a double inset. The app shell's body pads 10 12 12, and `IndexList` (T1) and the bare `RecordCockpit` (T2) inset again inside it, so AUD-01 sat 12 px in and 10 px down, and AUD-02/03's audit bar sat at 56 with the panes at 125 (handoff 46 / 115). Both now take back the body's padding inside `[data-shell=cols]`; the rail gains the spec's "Overview ⌄" band (`RecordRail.linksTitle`). DEC-908. Re-measured: AUD-01 a–h 0.64 to 2.54 (d now locks), AUD-02 1.13 to 6.37, AUD-03 2.97 to 12.78 (e now locks). Row order (DEC-340), the Source Documents sort (DEC-341) and the kit row heights stay; recorded in DEC-908 and the contracts. Checks: kit vitest (jsdom) 235/235, screen and domain vitest 249/249 (AUD-01/02/03, ENG-01, CLI-01/04/08, SIG-01, BND-01, ENG-05), Tier D 64/64, TPL-01/02 specimen parity 5/5.

- 2026-10-29 (row heights): the kits keep their defaults and gain `tight` (DEC-908): rail link and phase rows at 44 (padding 5), and Source Documents cockpit rows min 44, padding 8 12 9 (AUD-02's spec). The audit cockpit's rail (AUD-02, AUD-03) and AUD-02's canvas use it. Re-measured: AUD-02 b / g 3.13 / 3.14 (from 3.55 / 3.61), a, c, e 3.13 to 3.19, f 6.01; AUD-03 e 2.99, still under. Nothing new locks. What keeps AUD-02 b / g over is the Source Documents order (DEC-341) and the OverviewCard's height. Kit tests for `tight` and `linksTitle` added. Checks: kit vitest 235 + 2 new, AUD-02/03 and domain vitest 86/86, Tier D audits 3/3, TPL-02 specimen parity 5/5.

- 2026-10-29 (close): AUD-03 masks the viewer (`[data-cockpit='dock']`) and, in d, the open dialog (`[data-overlay='dialog']`). Mask selectors now match page-wide and keep the boxes that overlap the shot, because dialogs are portaled out of the shell. Re-measured AUD-03 a 2.91, b 2.91, c 2.81, e 2.92, g 2.93 (locked), d 7.51, f 3.18. A-01-T28 closes on AUD-01 a–f and AUD-03 a, b, c, e, g; AUD-02 a–e and g, AUD-03 d and f move to A-01-T33 in S34 after P-09-T18 (DEC-909; backlog, epic and sprint plan updated). Status: done.
