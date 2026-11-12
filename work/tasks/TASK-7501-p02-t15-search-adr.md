---
id: TASK-7501
title: P-02-T15 ADR P-33 Search in Postgres (ADR-241)
plan_key: P-02-T15
spec: SPEC-000  # ADR task
acceptance_criteria: [AC-1]  # the ADR records tsvector and pg_trgm under RLS and visible(), metadata-only projections and no hidden-by-wall counts
risk_zone: amber
status: in-review
branch: p02-t15-search-adr
worktree: /Users/ayushkbhatia/Accrued/abacus-s39
created: 2026-11-12
updated: 2026-11-12
---

## Objective
Draft ADR P-33 from chapter 09 P-33, DEC-42, DEC-43 and DF-14, number it on `main` and register it.

## Plan
- `docs/adr/ADR-241-search-in-postgres.md` (proposed). The plan alias ADR-211 is not a reservation;
  ADR-238 to ADR-240 were reserved by the S34 to S37 kickoffs, so the next free number is ADR-241.
- `docs/adr/backlog.md` P-33 row and minted list; `docs/adr/README.md` index row.
- DEC-4501.

## Partial
- Acceptance is Ayush's (amber ADRs never default on silence). P-02-T01 builds on it as proposed,
  behind `search.palette` (default off), as P-05 did on ADR-236.

## Progress log
- `2026-11-12` — ADR-241 drafted (DEC-4501): Postgres FTS + trigram, metadata only, visibility
  at query time, no hidden-by-wall field, POST-only search text, operational recents, C15 v1
  registration, refused principals.
- `2026-11-12` — ADR-241 accepted by Ayush (DEC-4529) after the S39 batch merged; status `accepted` in the ADR, the index and the backlog.
