---
id: TASK-8006
title: "C-01-T06: consumer contract tests for the closes stubs"
spec: SPEC-655
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: c01-t06-consumer-tests
worktree: /Users/ayushkbhatia/Accrued/abacus-s44
created: 2026-11-14
updated: 2026-11-14
plan_key: C-01-T06
---

## Objective
consumer contract tests for the closes stubs.

## Plan
1. [x] `backend/tests/contracts/closes/` on behalf of C-02, K-04, I-01, P-08, P-02, W-02: shapes, enums, 501 bodies, flag-off 404, `register_status_guard` fails closed, portal DTO has no firm-only field.

## Progress log
- `2026-11-14` — Planned at the S44 kickoff (TASK-8000).
- `2026-11-14` — Built: `backend/tests/contracts/closes/test_closes_consumers.py`: the fields C-02 (record, commentary, sync line, entries, recordings), K-04 (board rows, procedure statuses), I-01 (tiles, summary), P-08 (portal questions), P-02 (rows) and W-02 (run rows) read; `CloseFacts`; six statuses and no "Closed"; the portal DTO has no firm-only field; every route published with one action and a 501 (46 routes); portal routes only under `/v1/portal/`; the status guard slot fails closed and takes one guard per guarded status; the contract doc names every route; refusal codes catalogued. Not run (end pass).
- **Partial.** Flag-off 404 is asserted per route at the end pass against the running app (needs the DB for `flag_enabled`); the solo edition runs the suite in the one CI, not "N's session".

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
