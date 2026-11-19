---
id: TASK-8734
title: "C-02-T20: Ledger console batch drawer read"
spec: SPEC-700
acceptance_criteria: [AC-9]
risk_zone: red
status: in-review
branch: s51p-c02-t20-drawer
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-02-T20
---

## Objective
Finish C-02-T20 (TASK-8709): GET /v1/posting-batches/{id} (CLS-11 b2) answers the batch's log row, authorised on its client entity through the console's own read (walls and an unknown batch 404).

## Plan (red)
1. integrations/ledger_console: register_batch_entity provider and posting_batch(ctx, id) over posting_log; exported from integrations api.
2. adjustments/posting.batch_entity registered (adjustments owns posting_batches; integrations never imports adjustments).
3. w1_contract posting_batch_route live through _log_row; make generate.
4. Unit test in test_c02t20_ledger_console.py.

## Progress log
- `2026-11-19` — Built. Sync now and Request reconnect stay on their own routes (C-01's LedgerSyncWorkflow, A-02's reconnect) by design; the connection pane's dependents list stays empty: no registry names which agents read a ledger connection yet. Gates and tests run once at the S51 end pass (build first, test last).
