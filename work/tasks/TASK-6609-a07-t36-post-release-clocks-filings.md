---
id: TASK-6609
title: "A-07-T36: Post-release clocks and filings: PostReleaseClocksWorkflow, the AU-C 265 due item, the filings tracker, report.released as the P-14 retention clock event"
spec: SPEC-644
acceptance_criteria: [AC-36]
risk_zone: amber
status: in-review
branch: s34-a07-t36
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: A-07-T36
---

## Objective
Golden clocks hold: an Oct 9 release gives Dec 8 for both clocks, Archive in 5 days on Dec 3, and
Overdue on Dec 9.

## Plan (amber)
1. `assurance/clocks.py` (new): archive (release + 60), AU-C 265 (release + 60), risk at ≤ 7 days,
   overdue the day after, the five timers, Form 5500 due and extended dates.
2. `assurance/filings.py` (new): list, open on an EBP release (once), update under
   `seen_version` with the EFAST2 acknowledgement as this engagement's evidence version
   (`filing.update`); audited `filing.opened`, `filing.updated`; outbox `filing.updated`.
3. `assurance/post_release.py` (new): `report.released` → the archive opens (A-07-T31's handler,
   chained), the filing row, AUD-22's AU-C 265 due date, the retention anchor
   (`extend_retention_for` on the engagement's stored versions, `report_release`), and
   `PostReleaseClocksWorkflow` (background; timers at 9 AM firm time; a timer whose clock has
   stopped — archive locked, 265 sent — passes silently; `archive.deadline_risk` to the leads).
4. Routes: GET and PATCH `/filings` live; AUD-24's release view lists the filings.
5. Registries: workflow, activity, subscription, `filing` audit owner, `archive.deadline_risk`
   catalogue entry (the kind existed), reviewed audit actions; `evidence.api.engagement_stored_versions`.
6. Tests: `tests/unit/assurance/test_a07t36_clocks.py` (the goldens).
Rollback: revert; the subscription and the workflow stop with it.

## Progress log
- `2026-11-10` — Built; ruff, pyright clean; the app imports. Tests not run (end pass). Partial:
  the replay history `post-release-clocks-v1.json` is recorded at the end pass (Docker); the
  timers fire at 9 AM CT on Temporal's clock (the synthetic firm's demo clock does not move
  workflow time).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3206 | Timers check state instead of signals; one event for both clocks; release anchors retention | no |
