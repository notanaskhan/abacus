---
id: TASK-8808
title: "C-02-T26: QBO vendor and payment read datasets (connections, read-only)"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-c02t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T26
---

## Objective
The Copperleaf sandbox and fake return 12 vendors with payments split check/ACH/card, and the connector still exposes no write-shaped method.

## Done
- Connector datasets vendors and vendor_payments (Vendor query; BillPayment then Purchase per period, paged by cursor); CDC maps Vendor and BillPayment/Purchase
- qbo_format parse_qbo_vendors (1099 flag, last-4 of a masked tax id, unmasked id refused) and parse_qbo_vendor_payments (method check/ach/card/cash by code; non-vendor purchases left out)
- LedgerSync pulls vendor datasets as riders of the month set when the connector reads them (runs end at the snapshot, 0900); pages checked as hostile content
- migration 0991 widens sync_runs.dataset CHECK
- fake_quickbooks_online answers vendor queries; Copperleaf recordings (12 vendors, check/ACH/card) in cas_delivery_slice
- unit tests test_c02t26_vendor_datasets.py

## Progress log
- `2026-11-20` — Plan (red): datasets, parsers, sync, migration, fake, tests; rollback revert + downgrade 0991. CONN-001 unchanged (GET only on /query). Security review and tests at the end pass. [verify] Intuit masks TaxIdentifier; ACH is named by PaymentMethodRef.
