---
id: TASK-9024
title: "C-02-T44: CLS-11 states b, b2, e and Export"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-c02-t44-cls11-states
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: C-02-T44
---

## Objective
Backlog row acceptance: "CLS-11b, b2 and e render at Tier C and each QBO id opens the transaction in a new tab with rel noopener." Export (the posting-log CSV) shipped in C-02-T35.

## Done
- Backend (additive): GET /v1/posting-batches/{id} carries entries[] (ref, description, amount, external_txn_ref, deep_link) from adjustments through a new integrations slot; deep_link is built server-side from QuickBooks' numeric id in the deployment's QBO environment (none for a non-numeric reference); the ledger console carries conflicts[] (the open closing-date conflicts)
- Seed: AUGUST_POSTED_BATCH posts at 10:20 AM as the handoff reads (closing date 10:22); the export adds august_entries; make fixtures
- CLS-11: rows open the O2 batch drawer (?batch=), entries link to QuickBooks in a new tab with rel noopener noreferrer, footer to CLS-07 (manifest path /closes/$closeId/adjustments); Conflicts band grouped by batch and date with Ask the client and Re-date dialogs (reason required), held batches read can't post; the pane shows a QuickBooks-set closing date as changed in QuickBooks Online
- Tests: 2 drawer and conflict tests in tests/integration/backfill/test_cv2_w1_posting.py (Postgres, 17 pass); CLS-11.test.tsx 21 (b, b2 acceptance, row opens drawer, e, ask, re-date); manifest and fixture suites 913

## Progress log
- `2026-11-27` — Built; tests pass. Parity at Tier C runs in the end pass.
