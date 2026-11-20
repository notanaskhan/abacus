---
id: TASK-8809
title: "C-02-T24: Posting failures and conflicts"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s52-c02t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T24
---

## Objective
AJE-03 fails on the inactive account, posts on Retry without a duplicate, and an Aug 31 entry against an Aug 31 closing date offers only ask-client or re-date.

## Done
- adjustments/posting_recovery.py: record_failure (closing_date_locked opens one closing_date_conflicts row), PostingBatchFailed (C16 posting_failed to the poster and the preparer), retry_entry + run_retry (one-entry grant, same idempotency key, finish_if_done sets the closing date once, resolved_failure_count), ask_client (lift_closing_date_request template row through send_templated), redate (close_approvals.redate_withdraw: approval_withdrawn, new date, out of the batch), carry_reversals, reverse_entry, export_file (deterministic JE import workbook), record_external
- run_batch calls record_failure and emits posting_batch.failed; PostingInput gains entry_id/grant_id (defaults keep histories); writer.book_close_date
- routes wired: retry, ask-client, redate, record-external, export; new POST /proposed-entries/{id}/reverse (proposed_entry.create)
- closes: IssueClass posting, subscribers posting_batch.failed (CLS-06 exception as the poster) and posting_batch.posted / close.created (reversal carry)
- template key lift_closing_date_request; reviewed audit actions
- unit tests test_c02t24_posting_recovery.py

## Progress log
- `2026-11-20` — Plan (red): recovery module, run hooks, routes, closes subscribers, template key, tests; rollback revert (no migration: 0950 already has the tables). make generate for the new reverse route, the DB-backed walk and the security review at the end pass.
