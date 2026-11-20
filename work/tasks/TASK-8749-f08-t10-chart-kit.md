---
id: TASK-8749
title: "F-08-T10: ChartKit C-36: hand-rolled SVG donut, bar, stacked, line, box plot, KPI tile, sparkline, ChartTooltip, View as table and CSV"
spec: SPEC-000
acceptance_criteria: []
risk_zone: green
status: in-review
branch: s51-f08t10
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: F-08-T10
---

## Objective
Every chart requires a comparisonBasis prop, donuts refuse more than four slices, no chart uses purple, and View as table shows the same numbers as the SVG.

## Plan (green)
1. `packages/ui/src/charts/` (new): types.ts (comparisonBasis required on every chart and card prop), scale.ts (plain-math linear and niceMax, --p1…--p4 fills with --d1…--d4 strokes, summaries, datum/series tables, toCsv), charts.tsx (Donut refusing more than 4 slices via devAssert plus an ErrorRow in production, Bar, Stacked, Line, BoxPlot, Sparkline; role=img with a generated summary; held mark stays, others 45%), tooltip.tsx (220 px ChartTooltip with an intent link), card.tsx (ChartCard header 44 / footer 28 with the basis and scope, ··· View as table through the E4 statement DataGrid, client-side Download CSV, Copy link intent; ChartKpiTile 72 px, value at text-kpi 22 px, delta in words with a glyph, green-ink only for an improvement).
2. Root export from packages/ui; the KPI tile is `ChartKpiTile` because C-19's `KpiTile` already owns the name.
3. Gallery: `specimens/charts.tsx`, registered as c-36-chart-kit for /components/c/C-36.
4. Tests: `charts/charts.test.tsx` (@ts-expect-error for a missing basis on Donut, Bar, KPI tile and card; the 5-slice refusal; no purple; View as table and CSV equal to the SVG's data-value numbers; KPI tile).
5. Rollback: revert the PR; no backend, no consumer yet.

## Progress log
- `2026-11-20` — Built, stacked on #2387; chart tests 8 pass, ui specimens + charts 33 pass, web gallery 83 pass, tsc and eslint clean. Not run: Tier A parity against a recaptured Component Sheet.dc.html#c-36 baseline (handoff folder absent) and scripts/bundle-budget.mjs (needs a production build; end pass). Gates and tests run once at the S51 end pass (build first, test last).
