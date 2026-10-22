---
id: TASK-389
title: C1 live - firm-wide work-item list on the list envelope, allowed_actions on the projection (F-03-T31)
spec: SPEC-025
acceptance_criteria: [AC-1]
risk_zone: amber
status: done
epic: F-03
plan_key: F-03-T31
branch: f03-t31-c1-live
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"GET /v1/work-items lists Brightwater Hale work items of all five kinds with per-status counts,
and the C1 consumer tests pass against live code."

## What changed
- `GET /v1/work-items?engagement_id=&kind=&status=&cursor=&limit=` (`work_item.read_metadata`):
  `engagements.list_work_items` filtered by `visible_scope(..., "work_item", ...)`, newest first,
  on the P-36 envelope (`kernel.listing`: keyset cursor, capped total, per-status counts with the
  status filter left out).
- Flag `engagements.work_items_api` (expires 2027-01-20): on locally, in tests and for synthetic
  firms; 404 elsewhere until P-07 wires ENG-01/02.
- `EngagementOut.allowed_actions` on `GET /v1/engagements/{id}` from `identity.allowed_actions`
  over the engagement actions.
- Contract `docs/contracts/work-items.md` updated; C1 consumer tests for the envelope and the
  field; Postgres tests (five kinds, counts, cursor paging). API client regenerated.
- Not done: a `version` on the projection (engagements carry no version column yet; P-07).

## Progress log
- 2026-10-22: built. Tests run in the batch's end-of-run CI.
