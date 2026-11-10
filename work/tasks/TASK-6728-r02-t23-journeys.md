---
id: TASK-6728
title: "R-02-T23: journey E2E for POR-08, POR-09 and POR-15 (j12 8, 10, scoped; j03 9b, 13, 17, 18, privacy; j04 13; j22 8; j05 P; j10 11) and three screen specs"
spec: SPEC-646
acceptance_criteria: [AC-8, AC-11, AC-21, AC-24, AC-26]
risk_zone: green
status: in-review
branch: s35-r02-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T23
---

## Objective
The named tests pass in fixture mode in CI and on staging with real auth, with INV-1 to INV-5 asserted on every step.

## Plan
- `apps/web/e2e/journeys/r02-support.ts` (new): open an artboard as its scenario's persona at 1400 or 390; the artboard's region; the white-label check.
- Personas `ben-ashby` and `victoria-lam` added to the harness.
- **J12** (`J12-client-portal.spec.ts`), at 1400 and 390:
  - "j12 8: Dana accepts AJE-1 and RJE-1, declines PAJE-1 and PAJE-2 with reasons and acknowledges the 22,250 net effect" (POR-08 e then e2).
  - "j12 8 (fixture): Ben asks about accrued expenses and Tess approves the August package" (a, d, b).
  - "j12 10: Dana comments on page 2, approves draft v4 and downloads the finals after release" (POR-09 a, b, c).
  - "j12 scoped: Meera Shah sees only her Ridgeline K-1 and Sam Ortiz has no Approvals or Deliverables".
- **J03**:
  - "j03 9b" (POR-15 a, b).
  - "j03 13" (POR-08 e, e2; the AUD-16 firm half fixme naming A-06).
  - "j03 17" (POR-09 c, POR-15 e).
  - "j03 18" (POR-15 d).
  - "j03 privacy" (POR-15 c; Dana's management grant opens no room).
- **J04** "j04 13" (POR-09 f; g/h fixme naming A-10).
- **J10** "j10 11" (POR-08 b).
- **Fixme with owners:** J22 "j22 8" and J05 "j05 P".
- `apps/web/e2e/screens/POR-08.spec.ts`, `POR-09.spec.ts`, `POR-15.spec.ts`: every built artboard at 1400 and 390 through `journey.step`, so axe and INV-1 to INV-5 run on each.
- Every non-fixture project is `test.fixme` until R-02's live swap (R-02-T28) and the batch deploy.

## Partials (flagged)
- **j22 8 and j05 P:** POR-08's fixtures (R-02-T19) draw no Granite Peak AJE-3 for Luis and no preparation statements for Carla Juniper, so both stay `test.fixme` naming their owners (R-02 fixture plus A-06 SUM; A-08's provider).
- **Steps walked on artboards:** the steps read each artboard's own state rather than clicking through one live flow; the clicks are held by the screens' Vitest suites. The full-stack and staging walks follow the live swap.
- **Staging with real auth:** after the batch deploy (R-02-T28).

## Progress log
- 2026-11-10: written; Playwright runs at the end pass.
