---
id: TASK-9018
title: "T-06-T69: Autumn tax flag hygiene: seven tax flags retire into entitlements"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s54-t06-t69-flag-hygiene
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: T-06-T69
---

## Objective
Backlog row acceptance: "make flag-calendar shows no T-04, T-05 or T-07 flag expiring before Thu Dec 28, 2028 or inside Jan 1 - Apr 20, 2029, the retired flags are gone from feature-flags.yaml with _flags.py regenerated, and a firm without the tax entitlement still gets 404 on every retired route."

## Done
- Retired from docs/architecture/feature-flags/tax.yaml (and _flags.py regenerated): tax.review_workspace, tax.individual_workpapers, tax.fiduciary_workpapers, tax.fiduciary_k1_release, tax.estate_workpapers into tax_returns; tax.entity_workspace, tax.workbook_run into tax_entity_returns
- Every gate reads the entitlement: workspace, worksheet, fiduciary, estate and workbook contracts, the return frame's tab registry (register_return_tab takes a module), TAX-02, the review workspace routes and EntityReturn (an entity form without tax_entity_returns shows the locked coordination view)
- Migration 1034: the module for every firm that had a retired flag on (flag-state rows kept as history)
- Flag-off tests replaced by entitlement-off tests (test_t05t04/t07t03 protected bundles, test_t04t55 frame tabs, t05t66 web test), never weakened; runbook test asserts the retirement
- Synthetic seed: tax_board grants tax_entity_returns beside tax_returns; slices drop the retired flags; fixtures and e2e drop them
- Renewal: not due in repo time. tax_agents.enabled and tax.entity_agents expire 2027-05-16, outside every release window (DEC-5069: registry dates are real, not the plan's 2028 calendar). No T-07 flag remains
- Tests: tests/integration/backfill/test_t06t69_flag_retirement.py (Postgres: 404 per retired route family without the entitlement, past the gate with it; 1034's own SQL)

## Progress log
- `2026-11-27` — Built. Backend unit tax/platform/scenarios 3,400 pass; integration 75 + 3; web 990. Red zone (protected registry): notanaskhan approves per the row.
