---
id: TASK-1811
title: AUD-01/02/03 parity and accessibility (A-01-T28)
spec: docs/screens/AUD-01.md; docs/screens/AUD-02.md; docs/screens/AUD-03.md
acceptance_criteria: [A-01 DoD parity]
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
