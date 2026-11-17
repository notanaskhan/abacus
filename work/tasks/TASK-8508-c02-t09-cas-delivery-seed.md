---
id: TASK-8508
title: "C-02-T09: Brightwater Hale scenario extension for C-02 with footing tests"
spec: SPEC-700
acceptance_criteria: [AC-6, AC-16]
risk_zone: green
status: in-review
branch: c02-t09-cas-delivery-seed
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T09
---

## Objective
Spec section: docs/plan/epics/C-02.md §5.3. Copperleaf AJE-01..06 lines and classes, batches with QBO id ranges and the resolved July failure, sync events, closing dates Jul 31 and Aug 31, package figures, the December 2026 close locked Jan 11, 2027 with TB v1 and schedules, 12 vendors with W-9 states, the 2025 batch, Bluestem empty, one attest-flagged CAS client, the tess-moreno and ben-ashby personas, fake QBO scripted write outcomes; footing tests.

## Plan (green)
1. `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/cas_delivery_slice.py`: data only, every figure from CLS-07/08/11/12/13 specs and the epic §5.3; rows the handoff only counts (AJE-01/02/04 lines, Jan–Apr batches, 2025 forms) kept as counts.
2. Figure book `tests/golden/scenario/brightwater_hale/copperleaf_cas_delivery_figures.json` and `tests/golden/scenario/test_c02t09_cas_delivery_figures.py` (9 tests: 20,020/34,920/35,300; balanced named lines and class limits; QBO 48213–48218; the posting log; 549,195.45 both sides; 27,795 and 31,455; 74,900, 25,680, 144,000; six of twelve reportable).
3. seed_contamination: 'Elena Ruiz Design' allowed by exact string.
4. C-02-T08's consumer fixtures now carry the handoff's AJE amounts (11,860 / 700 / 2,140 / 5,320 / 14,900) and July's QBO 47602–47607 (the T08 commit had placeholders).

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5508). The 9 footing tests pass (run once here: a cheap pure-data suite). Loading the slice into the database lands with the services (C-02-T12, T20, T21, T45). Gates and tests run once at the S49 end pass (build first, test last).
