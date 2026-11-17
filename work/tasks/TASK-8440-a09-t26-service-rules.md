---
id: TASK-8440
title: "A-09-T26: rest: the service rules restated independently; a blank reopen reason is refused"
spec: SPEC-658
acceptance_criteria: [AC-4]
risk_zone: amber
status: in-review
branch: s48r-group-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T26
---

## Objective
A-09-T26's suite named structure freeze, lock blocks edits, reopen needs a reason, missing-TB refusal, the pull-all reauth path and the posting CHECK and target, but tested none of them itself. They are now restated from SPEC-658 against the database; writing them found that a whitespace-only reopen reason passed (the DB only checks NOT NULL).

## Plan (amber)
1. Security tests: finalized and locked structures refuse save; blank and whitespace reopen reasons refused and the lock stays; finalize refuses a missing TB; a refused token leaves Needs reauth and finalize still refuses; four posting CHECK/target refusals plus the one allowed elimination posting.
2. ledger.consolidation.reopen raises ReopenReasonRequired (422 reopen_reason_required) on a blank reason; exported from ledger.api.

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5428). The DB CHECK stays (no migration): the service refuses first, and the route's min_length=1 now cannot be met by spaces alone. Gates and tests run once at the S48 end pass (build first, test last).
