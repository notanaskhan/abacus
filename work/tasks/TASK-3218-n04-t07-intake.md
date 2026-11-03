---
id: TASK-3218
title: N-04-T07 notice intake service (create, correct and confirm, Create notice, discard)
spec: SPEC-000  # row (N-04 has no SPEC yet)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T07
branch: s26-n04-t07 (stacked on s26-p11-t21)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"The Santos CP14 fixture yields eight matched fields, a 0.71 respond-by blocks Create notice with
409 until confirmed, and the notice is created as New by Grace Holloway."

## Plan (amber)
- `notices/intake.py`:
  - `create`: `extracting` when form extraction covers the firm, else `manual_entry`;
  - `update`: corrections and confirmations as new human value rows; never a typed TIN;
  - `create_notice`: 409 `not_ready`, `low_confidence_unconfirmed`, `duplicate_unresolved`,
    `no_notice_engagement`; the work item, the notice columns, Received, the intake created;
  - `discard`.
- `engagements.api.notice_engagement` (QN-1 lookup).
- Routes: create, read, update, create notice and discard are live; attach stays 501.
- Tests:
  - `tests/unit/notices/test_n04t07_intake.py`;
  - the N-04-T02 stub test, adjusted for the patch N-04-T06 serves.

## Progress log
- 2026-11-03: built. Partial:
  - the Temporal `NoticeIntakeWorkflow` (it waits on `evidence_text.ready`, and C4 v1.1's fields
    are still 501, P-11-T22);
  - the client match by TIN and name, return match and authorization lookup (the sheet shows
    the person's pick);
  - duplicate detection;
  - creating the QN-1 engagement (409 until ENG-01 creates it);
  - notifications;
  - NoticeResponseWorkflow start.
  The work item is created in engagements' own unit of work, then the notice and intake in this
  one. Tests at the S26 end review.

## Decisions made during this task
DEC-2218.
