---
id: TASK-1286
title: AUD-06 trial balance tab in fixture mode, states a and c (A-02-T09)
spec: SPEC-333
acceptance_criteria: [AC-5, AC-8, AC-14]
risk_zone: green
status: in-review
epic: A-02
plan_key: A-02-T09
branch: s9b-ledger-tb
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"AUD-06a and AUD-06c pass their Vitest scenarios, clicking KRS Target 2045 lights its trust-report
row within 360 ms, and no code path sums a column in the browser."

## Plan
- `apps/web/src/screens/AUD-06/TrialBalance.tsx`: `useTrialBalancePane(engagementId)` returns the
  T2 canvas (header pills, R2 TB chip, Trial Balance · Leadsheets and layer segmented controls,
  check strip, evidence-grammar table with chips, ticks and flags, provenance caption) and the
  selected line's citation as the Viewer dock's target (`GET /v1/citations/{id}`).
- `screens/AUD-02/index.tsx`: the Trial Balance rail row draws that canvas behind
  `ledger.tb_workpaper`; the dock's Viewer becomes SHL-08's `ViewerPane` on the linked citation.
- `screens/AUD-06/artboard.tsx`: Northwind frames are the cockpit; the others draw the pane alone.
- Fixtures: `aud06Citations` (each fund line's citation is the Harborline row of its name), the
  cockpit, trust and capability handlers on the Northwind scenarios.
- `docs/screens/AUD-06.md`; manifest note. No backend, no generated files, no migration.
- Tests: `TrialBalance.test.tsx` (a, c, the linked row, the layer tooltip, the flag gate, no
  browser sums); `AUD-06.test.tsx` frame assertions moved from the interim frame's words.
- Rollback: revert the commit; the cockpit falls back to Source Documents with the flag off.

## Progress log
- 2026-10-26: built. Vitest: AUD-06 (28), AUD-02, SHL-08, gallery, routes, C9 contract (263 in
  23 files) pass; tsc clean (after `build:types` of the api-client: a fresh worktree has no
  `packages/api-client/dist`, so tsc checked the generated sources and reported 12 errors there);
  eslint and prettier clean on the touched files. Playwright not run (chromium 1243 not cached).
  Decisions in DEC-395 (named-totals placement, caption without review facts, the fixture
  citations, the flag gate).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-395 | C9 v1 gaps the screen works around (totals position, caption review facts) and the fixture citation alignment | No |
