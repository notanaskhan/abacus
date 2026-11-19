---
id: TASK-8728
title: "S51-END: S51 end pass: gates, suites, security review and fixes"
spec: SPEC-000
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-review
branch: s51-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: S51-END
---

## Objective
Run the S51 gates and suites once at the end (build first, test last), fix what they find, review the red work (W1 posting, ledger writes, consultations, destruction, platform writers) for security, and record what is carried to S52.

## Plan (amber)
1. make check-fast; make check-fast-frontend; build:portal; vitest on touched screens.
2. Unit suite (-n 4); schema_check up/down/up for 0980-0984; S51 DB integration tests (C-01-T44, Q-05-T31, Q-05-T09) and tenant isolation for the new tables.
3. Fix: 0984 table-wide UPDATE (column grant only), generated tenant-isolation tests, OpenAPI and client regenerated, audit actions reviewed, target kinds placed (ledger_write_operation under its client entity, destruction_batch firm-level), PostingBatchWorkflow replay history recorded, secrets allowlist for CLS-08 line keys, error-codes registry rewritten.
4. Security: posting idempotency scoped by key, poster and work item; posting-log CSV neutralises formula leads in provider references (ADR-052); W1 console reads authorise through entity_connections (walls 404); matrix denies agents on consultation positions and resolutions; 0980/0982 writers execute as abacus_ops only.
5. Main's own reds fixed on the way: platform_staff_token_url renamed platform_staff_exchange_url (not a secret; matches identity_exchange_url), console BFF refresh/sign-out classified as non-creating, ServiceLine Literal order aligned (typing's Literal cache made the OpenAPI enum order depend on import order).

## Progress log
- `2026-11-19` — Gates green (check-fast rc 0; frontend tsc/eslint/prettier, portal build and 787 vitest tests pass); unit suite 61153 passed with 12 reds, all fixed and re-run (9234 passed on the touched areas, 43078 on api/kernel/identity); schema_check reversible after the 0984 fix; CAS load and isolation 18 pass after seeding Copperleaf plan v1. Local only: the two WeasyPrint classification tests need libgobject (CI has it). Carried to S52: Copperleaf plan v1 as the Close Planner's draft (it loads as an empty published v1, DEC-5722), a proposed-entry decision outcome event for the override rates (the unemitted proposed_entry.decided subscription was removed), and the partials recorded on TASK-8700 to TASK-8727. Gates and tests run once at the S51 end pass (build first, test last).
