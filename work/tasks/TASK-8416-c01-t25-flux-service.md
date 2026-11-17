---
id: TASK-8416
title: "C-01-T25: Flux service"
spec: SPEC-655
acceptance_criteria: [AC-48, AC-49]
risk_zone: amber
status: in-review
branch: c01-t25-flux-service
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: C-01-T25
---

## Objective
Spec section: docs/plan/epics/C-01.md §3 F7. Flux service: month over month and year over year sets over the income statement with the shared dual-threshold engine and the firm's close_flux variance row; not comparable without a prior; a person's sealed explanation under If-Match; a Manager or Partner accepts (Senior 403, agent never); Excel export.

## Plan (amber)
1. `closes/flux.py`: `compute` (a new `analytic_sets` version only when the inputs hash changes; lines insert-only, statuses carried from explanations), `flux_set` (FluxSetOut with explanations, counts and the threshold label), `explain` (a new sealed `analytic_explanations` version, If-Match = row version), `accept` (human Manager/Partner through `authorise(flux.accept)`; emits `analytic_line.accepted`), `export` (safe_xlsx).
2. Routes in `contract_work.py`: GET flux and flux.xlsx (budget basis 404 until a budget import), PUT explanation, POST accept; `explain` (agent mode) stays for C-01-T30.
3. Tests: `tests/unit/closes/test_c01t25_flux.py` (AC-48's August lines, yoy dashes, periods, ids).

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5411). Lint and pyright clean. Adjusted figures: the snapshot's monthly activity plus the close's live AJEs (pending, approved, client approved) not yet recorded in QuickBooks, in natural sign. Partial: drivers are empty until C-01-T30's mode `flux` writes them; the budget basis answers 404 (no budget import exists). Gates and tests run once at the S48 end pass (build first, test last).
