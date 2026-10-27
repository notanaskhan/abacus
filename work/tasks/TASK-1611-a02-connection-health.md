---
id: TASK-1611
title: ConnectionHealthWorkflow, the daily refresh and health pass (A-02-T25)
spec: SPEC-333
acceptance_criteria: [AC-44]
risk_zone: red
status: in-review
epic: A-02
plan_key: A-02-T25
branch: s13-a02-t25
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Daily refresh and health on live provider connections: needs_attention vs needs_reauth by failure code, one notification per transition, reauth-due notices, no pull while attention is needed.

## Plan
- `connections/health.py` (activity `connections.check_connection_health`), `ConnectionHealthWorkflow` in `connections/workflows.py`, Schedule `connection_health:platform` (daily) in `connections/api.py` `SCHEDULES`.
- Events `connection.needs_reauth`, `connection.reauth_due`; notification catalogue mapping onto the existing kind `connection_needs_reauth` with messages.
- Migration 0271: `connections.reauth_noticed_for` and its update grant; registry and model.
- DEC-708 (one platform pass rather than per-tenant continue-as-new).
- Test `tests/integration/backfill/test_a02t25_connection_health.py`. The replay history `connection-health-v1-checked.json` is recorded in the batch pass.
- Rollback: delete the Schedule; downgrade 0271.

## Progress log
- 2026-10-27: built. Also rewrote N-01-T06's migration test helper without dynamic SQL (SUPPRESS-001 refuses the noqa).
