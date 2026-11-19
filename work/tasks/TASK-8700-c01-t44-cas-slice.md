---
id: TASK-8700
title: "C-01-T44: Brightwater Hale CAS slice through the closes services (copperleaf holdout)"
spec: SPEC-655
acceptance_criteria: [AC-13, AC-17, AC-20]
risk_zone: amber
status: in-review
branch: c01-t44-cas-slice
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-01-T44
---

## Objective
The `cas` slice (`--slice cas`, after `binders`) loads CLS-01's August portfolio through the closes services: the Café with Square/Shopify template through the import, Copperleaf's plan v2 and v3 (Raj drafts, Priya publishes) and draft v4 (savings statement on the bank feed, seven requests a month), the rest of "2026 Close" (twelve closes), the seven open CLS-06 exceptions, and the twenty-one other August closes with their pairs and statuses (3 + 11 + 5 + 3). `--holdout copperleaf` drops every Copperleaf event, so J02 creates the client.

## Plan (amber)
1. closes/seed.py: seed_synthetic_close_status (synthetic firm only; Not started to the CLS-01 status once; audited, emits close.status_changed).
2. closes/api.py exports the plan, template, generate and assignee services the loader calls (no new routes).
3. cas_slice.py: events after the binders setup; plan publishes before the generator so no generated close is pinned early; holdout by client.
4. loader.py: five handlers (`closes.template_imported`, `plan_version_seeded`, `year_generated`, `exception_seeded`, `portfolio_close_seeded`), each idempotent (template key, version read, work_item_exists, engine source dedupe).
5. Tests: tests/unit/synthetic/test_c01t44_cas_slice.py (events, holdout, counts, fixture-equals-seed against apps/web close-book.ts); tests/integration/test_c01t44_cas_loaded.py (DB load, second load writes nothing, holdout).
6. Rollback: drop the slice from SLICE_NEEDS; nothing else reads it.

## Progress log
- `2026-11-19` — Built: seed status service, api exports, the `cas` slice and its loader handlers, unit + DB tests. Partial (carried in this log): the Close Planner's v1 draft (no discard path for a superseded draft), CLS-06's four notes (no copy in the handoff), the fake QBO company, statement/payout/payroll files, Run 1 and Run 2 events, flux sets and the three transaction questions; CLS-09 history dates (v2 Mar 6, v3 Jun 2) stay fixture-side (DEC-5700). The subscription row is appended at the end of v3 rather than after Accrued Expenses (add_row appends). Gates and tests run once at the S51 end pass (build first, test last).
