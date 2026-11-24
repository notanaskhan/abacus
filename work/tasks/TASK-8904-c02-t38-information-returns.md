---
id: TASK-8904
title: "C-02-T38: Migration closes_information_returns"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-c02t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-22
updated: 2026-11-22
plan_key: C-02-T38
---

## Objective
vendors_1099 with sealed TIN refs only, vendor_payment_rollups, insert-only w9_requests, tin_match_results and backup_withholding_events, information_return_batches, insert-only information_returns. Acceptance: up/down/up passes, no column can hold a full TIN, and the insert-only tables reject UPDATE and DELETE.

## Done
- Migration 1013 (closes): 7 tables, forced RLS, column grants
- vendors_1099 TIN: tin_sealed (envelope), tin_last4 (4 digits), tin_kind, tin_fingerprint, whole-or-none CHECK, one TIN per entity (unique fingerprint); W-9 on file needs its evidence and signed date; person/agent-adopted sources need the person
- w9_requests: vendor_link refused by a named CHECK until R-03
- tin_match_results source manual, recorded by the acting person; backup_withholding_events started only at 24%, B-notice needs its date and evidence
- information_return_batches: one per entity and year, each status step needs its person, time and artefact (approval, IRIS file hash, receipt, acknowledgement evidence)
- closes registry, schema snapshot, tenant list
- tests/integration/test_c02t38_information_returns_migration.py (3 tests; end pass)

## Progress log
- `2026-11-22` — Built in the S53 sequential stack (DEC-5906).

## Plan (amber)
1. `1013_closes_information_returns.py` on 1012. 2. closes registry + snapshot + tenant list.
3. Rollback: downgrade drops seven new tables; nothing existing changes.
