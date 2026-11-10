---
id: TASK-6703
title: "P-05-T11: AUD-29 backend in audit_trail: engagement query and CSV export, activity catalogue and ACTIVITY_KINDS, segments, keyset paging, label search"
spec: SPEC-650
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34, AC-35, AC-36, AC-37, AC-38]
risk_zone: red
status: in-review
branch: s35-p05-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-05-T11
---

## Objective
The Northwind seed returns 23 events newest first with counts 12, 11 and 0, a Materiality search returns its rows, and the CSV carries no Restricted value and is audited.

## Plan (red)
1. `audit_trail/engagement_activity.py` (new): AUD-29 over ADM-07's explorer (`shown_to`, labels,
   `row_of`), narrowed to the engagement (`explorer.ENGAGEMENT`), so walls, `visible()` and the INV-1
   marker rule are the explorer's. Segment expression (agent, or system with a run → via_agent;
   policy; else human); counts over the filter without the segment; keyset on
   `(effective_at, seq)` descending; categories through the catalogue over the engagement's distinct
   actions; search through `labels.matching` inside the query; export streams pages into CSV with
   `exports._cell` neutralisation, no values column, cap 10,000, and records `audit_event.exported`
   (`filter_sha256`, `row_count`) on the engagement.
2. Activity catalogue for AUD-29: `ACTIVITY_LINKS` (link kind, search keywords, in_activity), prefix
   entries, `register_activity_links` for later modules' `ACTIVITY_KINDS`; collaboration hidden except
   `todo.deleted` and `comment.redacted` (OQ-4).
3. `audit_log_contract.LinkKind` gains `sign_off`, `materiality`, `document`, `risk`, `gate`, `todo`
   (additive; ADM-07 still uses `run`/`none`). `activity_catalogue`: `audit_event.exported` (export).
4. Routes in `engagement_activity_contract.py` call the service; `errors=(501,)` stays declared.
5. The P-05-T08 suite's strict xfails removed (they would XPASS).
6. Tests: `tests/unit/audit_trail/test_p05t11_engagement_activity.py`; the AC suite
   `tests/integration/backfill/test_p05t08_activity_ac.py`.
7. Rollback: revert; the flag `audit_trail.engagement_activity` stays off.

## Partial
- **Labeler gap-fill (R-3):** only the `user` labeler is registered on main; other target kinds
  show identifiers. The label indexer calls labelers without a tenant (`audit_labels(None, …)`), so
  an engagement or document labeler needs a slot change (tenant on the call). That is Q-03-T235's
  call-off ("only if G-02 shipped ADM-07 without read-time value resolution"), not built here.
  Search still matches people's names and the action's words ("Materiality decided").

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass). Make generate needed for `LinkKind`.
