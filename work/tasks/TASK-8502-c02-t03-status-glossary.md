---
id: TASK-8502
title: "C-02-T03: Status vocabulary and glossary rows for posting, delivery, hand-off and information returns"
spec: SPEC-700
acceptance_criteria: [AC-20]
risk_zone: amber
status: in-review
branch: c02-t03-status-glossary
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: C-02-T03
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.6, §4.7 (DF-23, DF-31, DF-19). Status words for posting batch, proposed entry Rejected and Recorded externally, close Approved/Delivered/Locked, deliverable, tax hand-off, W-9, e-file record; glossary rows; C2 regenerated.

## Plan (amber)
1. `docs/product/status-vocabulary.yaml`: proposed_entry + recorded_externally (Recorded in ledger; attest Recorded by {client}); new objects posting_batch, closing_date_conflict, ledger_write_grant, close_deliverable, tax_handoff (not_available and ready derived), w9_status, information_return_batch. Close approved/delivered/locked and proposed_entry rejected were already there.
2. Regenerate `_statuses.py` and `packages/ui/src/status.gen.ts`.
3. Glossary section 'ledger posting and CAS delivery': posting result, write operation, write grant, firm write capability, closing date, recorded externally, close package, tax hand-off, information return, W-9 request.
4. Rollback: revert; words only.

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5502). Codegen clean. Gates and tests run once at the S49 end pass (build first, test last).
