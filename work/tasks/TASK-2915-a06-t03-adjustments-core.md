---
id: TASK-2915
title: A-06-T03 migration 0643 adjustments_core (C8 tables)
spec: SPEC-642
acceptance_criteria: [SPEC-642 AC-1, AC-2]
risk_zone: red
status: in-review
epic: A-06
plan_key: A-06-T03
branch: s24-a06-t03 (stacked on s24-a06-t02)
worktree: /Users/ayushkbhatia/Accrued/abacus-s24
created: 2026-11-01
updated: 2026-11-01
---

## Objective

The adjustments module's first tables: proposed entries and lines, insert-only decisions and approval batches, with posting dormant.

## Plan

- Migration `0643_adjustments_core` (expand-only, on 0642): `proposed_entries` (status CHECK from the vocabulary, `pe_posting_dormant`, `pe_attest_review_required`, agent-created rows name the person), `proposed_entry_lines` (debit xor credit; deferred constraint trigger `unbalanced_entry`; `entry_locked` trigger once the entry leaves the open states), `proposed_entry_decisions` and `approval_batches` (insert-only, human-only bound to the session's actor; a batch's approver is the session's own person; a recorded decision names evidence; a rejection names a reason). Forced RLS; no DELETE except lines while open.
- `adjustments/registry.py`: tables, insert-only, insert and update columns.
- Test: `tests/integration/test_a06t03_adjustments_core_migration.py`.
- Rollback: the downgrade drops the four tables and both functions.

## Progress log

- 2026-11-01: built in abacus-s24, stacked on A-06-T02. Tests written, not run.
