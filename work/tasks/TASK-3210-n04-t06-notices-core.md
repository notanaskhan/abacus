---
id: TASK-3210
title: N-04-T06 notices module core (status machine, NOT-01 index and summary, detail, assign, start)
spec: SPEC-000  # row (N-04 has no SPEC yet)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: N-04
plan_key: N-04-T06
branch: s26-n04-t06 (stacked on s26-a06-t19)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"HOME-01 and NOT-01 read 9 open and 2 New from one provider, a walled user gets 404 with
recomputed tallies, and every illegal transition answers 409 with facts."

## Plan (amber)
- `notices/service.py`:
  - `TRANSITIONS` and `move` (with the event row; 409 `illegal_transition` with
    from_status/to_status facts);
  - `visible_notices` under `visible(notice.read)`; deadline-risk sort; `tallies` (QN-6 tiles,
    open, due within 7, blocked); `notice` (404 when walled);
  - `edit` (If-Match; a corrected respond-by); `start`; `activity` from audit events.
- Routes: list, summary, detail, patch, start and activity are live; the rest stay 501.
- `kind.status` reads the notice's status. `register_home_count('notices')`
  (`notices/home_counts.py`).
- Tests:
  - `tests/unit/notices/test_n04t06_core.py`;
  - `tests/integration/backfill/test_n04t06_notices_core.py`.

## Progress log
- 2026-11-03: built. Partial:
  - `work_items.due_on` sync (engagements exposes no due-date writer yet);
  - the search projection;
  - the retention record type;
  - the masked TIN on detail (it arrives with the intake, N-04-T07).
  - `notices.api` consumers (CLI-05, portal, T-08, R-03) read the same service when they land.
  Tests at the S26 end review.

## Decisions made during this task
DEC-2210.
