---
id: TASK-8085
title: "A-08-T20: Shared dual-threshold flux engine (workpapers/compute/flux.py)"
spec: SPEC-657
acceptance_criteria: [F3]
risk_zone: amber
status: in-review
branch: a08-t20-flux-engine
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T20
---

## Objective
One pure flux engine for AUD-13, AUD-26 and CLS-10: both legs required on the absolute change,
derived lines computed and footed but never evaluated.

## Built
`workpapers/compute/flux.py` (exported as `workpapers.api.evaluate_flux`, `FluxLine`,
`Thresholds`, `FluxSet`, `FluxRow`); `tests/unit/workpapers/test_a08t20_flux_engine.py` (5 pass:
Granite Peak 8 of 14 with interest within, Lakeshore only Grants, Copperleaf through the same
engine, derived lines, the zero-prior rule and the hash). C-01-T25 (S48) builds the close's flux
service on it (OQ-1 settled: the engine lives in workpapers).

## Progress log
- `2026-11-15` — Built (DEC-5067).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5067 | Both legs on the absolute change; zero prior leaves the amount leg alone; percent half-up to 0.1 | no |
