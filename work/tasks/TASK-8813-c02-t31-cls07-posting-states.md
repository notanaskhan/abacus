---
id: TASK-8813
title: "C-02-T31: CLS-07 posting states c2, d, e, f, g"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s52-c02t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T31
---

## Objective
CLS-07c2, d, e, f and g render at Tier C, and no live route can render frame f or a Post control for an attest client.

## Done
- c2 from the dry run (entity, total, closing-date sentence) and the post with Idempotency-Key; d banner with batch, count, total, closing date and time, View in ledger sync; rows Posted · QBO n; e red pill, the failure line by code and Retry (retryEntryMutation); g attest rows held and no Post or Retry; f stays fixture-only (the label comes from the seed's frame alone)
- C8 v2 additive: row posting_batch_id, failure_line, allowed_actions; tallies posted_batch_id/count/amount/at, closing_date_set, resolved_failure_count; close_approvals fills them (the live read now carries external_txn_ref and reverses_on too)
- fixtures dry run, post, retry; api-client regenerated
- CLS-07 tests for d, e, g

## Progress log
- `2026-11-20` — FE + additive contract; vitest at the end pass.
