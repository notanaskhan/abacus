---
id: TASK-1247
title: J04-PBC slice and J01-core skeleton journey specs (F-04-T32) and the local screen parity report (F-04-T33)
spec: SPEC-307
acceptance_criteria: [AC-8]  # fixture mode; F-04-T32 and T33 are F-04.33 and F-04.34 (no spec AC of their own)
risk_zone: green
status: in-progress
epic: F-04
plan_key: F-04-T32; F-04-T33
branch: s8b-quality
created: 2026-10-25
updated: 2026-10-25
---

## Objective
T32: "j04-fs-audit PBC slice is walkable on staging by Mar 5 and the Sep 24 snapshot is loaded for
Pilot 0." T33: "Report lists artboard, diff, tier and lock, blocks on tier A and D failures and
commits no PNGs."

## Built
- `apps/web/e2e/journeys/J04-fs-audit.spec.ts`: the PBC slice at the Sep 24 snapshot (2026-09-24
  09:00 CT). Step 1 (Luis Ferrante, Granite Peak's CFO, at the portal sign-in, POR-01a) walks in
  every project; steps 2 to 6 (binder request BND-02/SHL-14, portal upload POR-03, scan, SHL-20
  screening, accept or return) are `test.fixme` with owners: P-06-T16 (S6), R-01-T10/T18 (S8,
  S10), P-06-T22 (S8).
- `apps/web/e2e/journeys/J01-firm-onboarding.spec.ts`: the J01-core skeleton. Step 1 (Margaret
  Okonkwo on ADM-01) walks in the fixture project (fixme elsewhere until E0 turns
  `firm_settings.v2` on); steps 2 to 5 (ADM-02, ADM-03, ADM-04, ADM-10) are `test.fixme` with owners
  G-01-T10, G-01-T14, G-02-T25, R-01-T28.
- `apps/web/e2e/parity/screen-rows.ts`, `screens.spec.ts`, the `parity-screens` Playwright project,
  `pnpm parity:screens`, and `parity-report/screens/{parity.json,index.html}` from the parity
  reporter: one row per artboard of each `fixture` or `live` screen (route registry statuses read
  from source; tiers and locks from each contract's `## Parity` table); Tier A and D block, B once
  locked, C report-only; an artboard without a baseline is `unmeasured`, never passed; Tier D rows
  point at `e2e/visual/tier-d.spec.ts`. Baselines are the fetched, git-ignored `.visual/` crops; no
  PNG is committed.
- `apps/web/src/routes/screen-parity.test.ts` (vitest) for the row logic.

## Progress log
- 2026-10-25: `ABACUS_FIXTURES=1 ABACUS_VISUAL_PORT=5291 playwright test --project=fixture` on the
  two journeys: 2 passed (the walkable steps, with axe and INV-1 to INV-5), 9 fixme.
  `pnpm exec vitest run src/routes/screen-parity.test.ts`: 8 passed. `pnpm parity:screens`
  (port 5291): 37 artboard rows over the 6 built screens with a Parity table, all `unmeasured` because no handoff
  baselines are on this machine (`ACCRUED_HANDOFF_DIR` unset, `.visual/` empty); ADM-01 (no
  contract file), SHL-01 and SHL-03 (parity in prose, no table) are listed as missing a Parity
  table. Not run: staging (not up), so J04's "walkable on staging by Mar 5" waits for staging and
  the five fixme steps' owners.
  **Human to-do:** the Pilot 0 PBC top-up at the Sep 24 snapshot is a staging load
  (`make seed-staging` under the deploy lock, runbook), which agents never run.
