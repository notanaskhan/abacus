---
id: TASK-8084
title: "A-08-T16: Confirmations core (migration 0894, create, list, summary, address verification, isolation)"
spec: SPEC-657
acceptance_criteria: [AC-6]
risk_zone: amber
status: in-review
branch: a08-t16-confirmations-core
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T16
---

## Objective
External confirmations under the auditor's control: positive-only drafts with book lines, the
AUD-14 log and summary (tiles, AR coverage), independent address verification with citations,
the send's address gate, and client isolation.

## Plan (amber: written before the build)
1. Migration **0894** `confirmations` (nine tables; insert-only verifications, events, responses,
   reconciliation items, alternative procedures and human-only decisions; the link table).
2. `assurance/confirmations_service.py`: create, log, summary (`coverage_of`), detail, export,
   verify_address, `check_sendable` (409 `address_not_verified`), the `confirmation` link purpose.
3. `confirmations_contract.py`: the T16 routes served; send runs the address gate before T18's 501.
4. `ConfirmationCreateIn.lines` (additive). Tests: unit (2 pass) and integration (end pass).
Rollback: revert; downgrade drops the nine tables; behind `audits.confirmations`.

## Progress log
- `2026-11-15` — Built (DEC-5066). The AR population is the newest year snapshot's balance on the
  accounts the AR confirmations name (through `ledger.api`); clearly trivial is 0 until A-08's
  materiality read joins (T18).
