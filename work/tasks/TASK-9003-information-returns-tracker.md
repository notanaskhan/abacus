---
id: TASK-9003
title: "C-02-T45: 1099 tracker backend"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s54-c02-t45-1099-tracker
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-26
updated: 2026-11-26
plan_key: C-02-T45
---

## Objective
The engine marks exactly six Copperleaf vendors reportable at $2,000, excludes Cascade Coffee's $41,260 card payments and keeps Hartwell & Lowe reportable as an attorney.

## Done
- closes/vendor_rollups.py: VendorRollupConsumer on ledger_snapshot.recorded (vendors_1099 rows and per-year, per-method rollups), the CLS-13 tracker (tiles, C21 rule text, rows), a person's vendor edit
- connections/vendor_datasets.py: a snapshot's vendor pages read from the store and parsed (read only)
- compute/information_returns.py: rents to 1099-MISC box 1 (paid_rents)
- migration 1032 (vendors_1099.paid_rents)
- routes: GET information-returns and PATCH vendors live (stubs retired)
- tax.api exports due_dates_for
- tests: 8 unit (row acceptance over the Copperleaf seed), 4 integration (rollup from stored pages, acceptance through the route, re-sync keeps a person's classification, empty year, team-only, no threshold 503)
- DEC-6009

## Progress log
- `2026-11-26` — Built; unit and integration tests green. The suggestion applier (C-02-T34) was already registered; T45 needed no second one.
