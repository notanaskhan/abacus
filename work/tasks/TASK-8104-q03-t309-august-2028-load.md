---
id: TASK-8104
title: Q-03-T309 August 2028 load content — entity returns, Workbench sessions, CAS closes, 1,500 SSE streams
spec: SPEC-655
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: q03-t309-august-2028-load
created: 2026-11-15
updated: 2026-11-15
---

## Objective
The August 2028 peak as a load profile on the service APIs (Q-03 §9).

## Plan (amber)
- `backend/src/abacus_tools/loadtest/scenarios/august_2028.yaml`: 1065 entity returns (return, sections, Schedule K and a line's breakdown, capital accounts, K-1 packages and the release check), Workbench sessions (list, read, one idempotent question), July 2028 closes (list, running, accounts, reconciliation, requests, flux, runs) and P-10's 1,500 SSE streams held 30 minutes (cut item 5 applied, P-10-T51).
- `tests/unit/tools/test_q03t309_august_2028.py`: every step is an OpenAPI operation with its method; the four loads; the only write; every group's p95.
- Rollback: delete the profile; nothing persists.

## Partly built
- The run on the perf stack (the row's acceptance) is not part of S46's build: the perf stack and its seed ids (`return_id`, `line`, `session_id`, `close_id`, `account_ref`, `topic`) are a human to-do.
- Note: the spec named in this file's header is the sprint's close-engine SPEC only for the docs validator; Q-03 has no SPEC row for T309.

## Progress log
- 2026-11-15: built; profile test green; stacked on #2103.
