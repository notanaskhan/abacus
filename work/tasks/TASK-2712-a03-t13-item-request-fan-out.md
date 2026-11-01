---
id: TASK-2712
title: A-03-T13 Item-request fan-out and requests.api.create_items_bulk
spec: SPEC-580  # A-03 F4 US-4.1 and docs/contracts/sampling.md §7.2
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-03
plan_key: A-03-T13
branch: s22-a03-t13
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "Creating from Version 2 writes exactly 125 requests (100 for Dana Kowalski, 25
  delegated to Sam Ortiz), a replay creates none, and a Draft version answers 409
  sample_not_approved."

## Scope
**In**: `sampling/item_requests.py` (preview, create with `Idempotency-Key`), the two routes,
`requests.api.create_items_bulk` (+ `BulkItem`, `delegate_item`, `ContactNotPortalUser` exported),
audit and error catalogue entries, contract §7.2, `test_app_gates` lists (the A-03 sampling and
mapping POSTs that main left out), stub test, HTTP suite.
**Out**: SHL-14 c and AUD-11 c (A-03-T15); the send and its per-recipient email grouping (P-06's
send reads `batch_id`); independent AC suite (A-03-T18).

## Plan (amber)
1. Requests come from an approved version; one request per (template, item); recipients must be
   the client's contacts; third parties must hold a portal sign-in, checked before any write.
2. One unit of work writes every request (`create_items_bulk`, which authorises
   `request_item.create` too) and the `sample_set.requests_generated` audit; each POR-14 request is
   then delegated through P-06's `delegate_item`, which issues the per-item grant (identity's own
   write).
3. `batch_id` and the item link ride in `linked_ref` (no schema change: 0100's column).
4. Rollback: revert; the routes return to 501 stubs; no migration.

## Progress log
- 2026-11-01: built; tests run in the S22 end pass. A delegation that fails after the requests
  committed leaves them undelegated and the key pending (409 on retry) — guarded by the up-front
  portal check; recorded in DEC-1763.
