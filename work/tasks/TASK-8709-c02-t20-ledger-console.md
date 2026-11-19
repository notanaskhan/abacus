---
id: TASK-8709
title: "C-02-T20: Ledger console API for CLS-11"
spec: SPEC-700
acceptance_criteria: [AC-23, AC-24]
risk_zone: red
status: in-review
branch: c02-t20-ledger-console
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-02-T20
---

## Objective
GET ledger-console, posting-batches (filters), posting-batches.csv (deterministic, audited) and ledger-activity for one client entity on the person's walls: connection health in CLS-11's words (a forced 401 reads Needs reauth), the client owner's write grant and who authorised it, the last sync, tiles (posted, proposed, failed post, resolved, closing date) and the activity timeline. A connection needing reauth refuses posting everywhere (connection_needs_reauth at dry run, batch and run).

## Plan (red)
1. integrations/ledger_console.py; posting facts through a provider adjustments registers (register_posting_log; integrations never imports adjustments).
2. w1_contract.py: four routes call the service (shapes unchanged).
3. integrations/writes.py: W1Ledger.needs_reauth; W1 refusal connection_needs_reauth (appended to the audited index).
4. adjustments/posting.py: posting_facts_for registered; reauth refused at dry run, batch and run.
5. Also on this branch (end-pass hygiene for C-02-T21): Account renamed LedgerAccount (glossary L12) and ignore reasons.
6. Tests: tests/unit/integrations/test_c02t20_ledger_console.py.

## Progress log
- `2026-11-19` — Built; unit tests pass (3), and the C-02 suites (104) still pass. Not built: the batch drawer route (/posting-batches/{id} stays 501; CLS-07's batch read answers it), Sync now (C-01's LedgerSyncWorkflow) and Request reconnect (A-02's reconnect route) are reached from their own routes; agents-using-it list (dependents) is left empty. DB-backed console test at the S51 end pass. Gates and tests run once at the S51 end pass (build first, test last).
