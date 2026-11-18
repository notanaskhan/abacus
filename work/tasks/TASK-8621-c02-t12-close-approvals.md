---
id: TASK-8621
title: "C-02-T12: Close approvals over C8 (adjustments/close_approvals.py)"
spec: SPEC-700
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: c02-t12-close-approvals
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: C-02-T12
---

## Objective
Spec section: docs/plan/epics/C-02.md §3 F2 (CLS-07). Close entry projection with tallies and approver context; named-human batch approval within class limits; held approval by manager or partner; request approval; reject; withdraw; 10-second Undo; behind adjustments.posting.

## Plan (red)
1. adjustments/close_approvals.py: close_entries (K-02 aje_classification_for now, tallies by code), approve_batch (all within threshold, batchable, non-attest, role meets level; else 409 over_approval_limit; A-06 create_batch with label Approved by <initials> under <policy>), approve_held (review required needs manager or partner; writes at once; undo_until +10 s), undo (own approval, inside 10 s, before any posting result), withdraw (approved, unposted, back to its threshold result), request_approval (C16 entry_approval_requested to a manager or partner; no decision row), reject (A-06 reject with the reason).
2. posting_contract.py: six C8 v2 routes wired to the service (close list, approve, request, undo, withdraw, reject-close); ProposedEntryStatus enums, no posting-status literals (A-06-T17).
3. integrations/posting_settings.py: posting_enabled_for (the integrations-owned switch, read through integrations.api).
4. decisions.py: public decide/set_status aliases for the shared writer.
5. tests/unit/adjustments/test_c02t12_close_approvals.py: approver levels and the Undo window.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5621). Partial: the class limit per row needs K-02 to return the payload row's limit with the outcome (row class_limit is empty until then); the CLS-06 issue on reject is the closes consumer's (C-02-T19); the DB acceptance (Raj batch, the 14,900 refusal, Priya's Undo) runs as integration tests at the end pass. Open in Excel stays 501 (C-02-T19 export). Gates and tests run once at the S50 end pass (build first, test last).
- `2026-11-18` — Completed (S50 round 2): K-02's EntryClassification now carries the listed class's `limit_usd`, and each CLS-07 row shows its class limit. The engagement authorise on every act landed in the S50 gate fixes (#2316).
