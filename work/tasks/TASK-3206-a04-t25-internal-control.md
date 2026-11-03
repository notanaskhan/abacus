---
id: TASK-3206
title: A-04-T25 internal control, the Exceptions sheet and the exception-route slot
spec: SPEC-620
acceptance_criteria: [AC-23]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T25
branch: s26-a04-t25 (stacked on s26-n04-t08)
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

## Objective
"Exceptions!D2 resolves to row 2 with two citations, Send to Findings answers 503 until A-06
registers its router and then routes in one unit of work, and no API path sets a concluded
severity."

## Plan (amber)
- Migration 0657 `assurance_controls_soc` on 0656:
  - `control_activities`, `walkthroughs` (insert-only, trigger) and `control_exceptions` (no
    concluded column; proposed severity with its proposer kind);
  - `soc_report_evaluations`, `soc_exceptions` and `cuecs` (served by A-04-T31).
- `assurance/internal_control.py`:
  - processes: list, get, add, and edit with a walkthrough (409 `version_conflict`);
  - the sheet (`Exceptions!D{row}`), `record_exceptions` (human or the agent's suggestion);
  - `propose_severity`;
  - `register_exception_route` / `route_exception` (503 `route_not_available`, 409 `no_amount`,
    `already_routed`);
  - `request_evidence` as a C5 draft item.
- Event `control_exception.recorded`.
- Routes: the T01 stubs now call the service. The route action is hidden until a router
  registers. Registry tables and `IMMUTABLE_TABLES["walkthroughs"]`.
- Test: `tests/integration/backfill/test_a04t25_internal_control.py`.
- Rollback: `alembic downgrade 0656`; revert.

## Progress log
- 2026-11-03: built. SOC evaluation service and CUEC mapping are A-04-T31. Tests at the S26 end
  review.

## Decisions made during this task
DEC-2206.
