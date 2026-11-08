---
id: TASK-6234
title: S31 partials round 2, end pass (gates, tests, security review, bookkeeping)
spec: SPEC-640
acceptance_criteria: [AC-1]
risk_zone: green
status: done
epic: A-05
plan_key: A-05-T58
branch: s31d-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s31
created: 2026-11-09
updated: 2026-11-09
---

## Plan
- `make check-fast`; the touched modules' unit, contract and security suites; the new migration
  tests and the schema contract against a local database; vitest; j03 and j04 fixture journeys.
- Security review of the new writes (related-party activity, the 4i render).
- Record what stays open (DEC-2829) and the round in `docs/plan/status/S31.md`.

## Progress log
- 2026-11-09: started.
- 2026-11-09: gates and tests, after fixes:
  - check-fast passes;
  - unit, contract and security suites pass, apart from the 8 WeasyPrint renders (no libgobject
    on this Mac);
  - the integration migration and schema tests pass (24 on rerun; the first run's 13 errors were
    Docker timeouts under load);
  - vitest 3,316;
  - j03 and j04 fixture journeys: 25 passed, 15 staging-only skipped.
- End-pass fixes:
  - L12 bans `activity` as a code name, so the record class is `PartyRecord`;
  - OWN-001 read `extract(year FROM …)` as a table, so the query uses `date_part`;
  - the 201 gate lists the 4i render;
  - error-codes.yaml names `schedule_period_unknown`.
- Security review: both new writes authorise first, are human-only and tenant-scoped, and have
  column-level grants. No findings.
