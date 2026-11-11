---
id: TASK-6735
title: "A-07-T41: Brightwater Hale completion-to-archive scenario (the `archive` slice) through the services"
spec: SPEC-314
acceptance_criteria: [AC-2, AC-4, AC-5, AC-6, AC-7, AC-8]
risk_zone: amber
status: in-review
branch: s35b-a07-t41
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T41
---

## Objective
make seed-demo and fixture mode show identical AUD-18 to AUD-25 data and the scenario writes only
through service APIs.

## Plan
- `abacus_tools/.../brightwater_hale/archive_slice.py` (new, `--slice archive`): Northwind from the
  rep letter's v1 (Oct 2, 8:20 AM) through the EQR's concurrence (Oct 5, 4:40 PM), v3's approval
  (5:10 PM), the report's L4 (Oct 7, 4:20 PM), the AU-C 260 letter (Oct 8), the bring-down
  (#4240, 9:04 AM), Dana's 9:12 AM signature, the 10:07 AM release, the Form 5500 filing
  (Oct 14), the readiness run (Oct 22), the AU-C 265/703 letter (Nov 20, acknowledged Nov 24), the
  lock (Dec 3, 4:18 PM CST) and the PI-02 addition (Jan 15, 2027); Granite Peak's going-concern
  card (Oct 26) and release (Oct 27); Lakeshore's review report draft (Nov 10).
- `loader.py`: one handler per kind, each calling the service (or the route's own check, then
  the service, where the service relies on its route); ReleaseWorkflow and ArchiveLockWorkflow
  dispatched as their routes do and awaited.
- `assurance/report_builder.py`: `set_report_date` (AUD-23's date and city; none existed, and
  the release reads the report date) and the report's kind from the engagement type (a review
  or compilation report used the audit template).
- `assurance/api.py`, `identity/api.py`: the services the slice calls.
- `epochs.py`: snapshots 2026-10-05T11:05, 10-09T10:05, 10-22T09:30, 12-03T16:20,
  2027-01-15T15:00. `fixture_export.py`: the 10:05 profile (AUD-22, AUD-23, AUD-24 reads).
- Tests: `tests/unit/scenarios/test_a07t41_archive_slice.py`,
  `tests/unit/assurance/test_a07t41_report_date.py`,
  `tests/integration/test_a07t41_archive_loaded.py`.
- Rollback: revert; the slice is opt-in.

## Partials (flagged)
- **AUD-18, AUD-19 and AUD-21 have no live reads:** their GET routes still answer 501
  (`completion_contract.py`'s `/eqr`, `/completion`, `/subsequent-events`, `/legal-letters`,
  `/going-concern`; `release_contract.py`'s `/representation-letter`), so those three screens
  cannot be exported, and fixture mode stays the TS seed's for them. The rep letter's send route
  is a stub too: the envelope is written as the provider would (DEC-3302).
- **The export stops at 10:05 on Oct 9:** the export loads with no relay or worker, so the release
  (a workflow), the archive it opens (a `report.released` consumer) and the lock (a workflow) run
  only under `make seed-demo SLICE=archive` with `make dev`. AUD-24 d and AUD-25 are not
  exported.
- The six digest cards, 26 workpapers, 14 notes and 23 run logs are what the earlier slices
  recorded; A-07-T43's goldens pin the numbers.

## Progress log
- `2026-11-11` — Built; unit tests written (the slice's own run green), the load test written,
  not run (end pass). Fixture JSON at the end pass (`make fixtures SNAPSHOT=2026-10-09T10:05`).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3302 | The archive slice's provider-side envelope, workflows dispatched and awaited, report date setter, report kind by type | no |
