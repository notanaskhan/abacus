---
id: TASK-8331
title: "W-01-T13: Integration health monitor"
spec: SPEC-659
acceptance_criteria: [AC-27, AC-28]
risk_zone: red
status: in-review
branch: w01-t13-health-monitor
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T13
---

## Objective
Spec section: docs/plan/epics/W-01.md F4.
Integration health monitor.

## Plan (red)
1. `integrations/health.py`: the pure transition rule and `apply_probe` (one firm install per unit of work: status, reason code, one integration event, the `integration.health_changed` outbox event and audit).
2. Audit kind reviewed. Tests: `tests/unit/integrations/test_w01t13_health.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5319). Lint and pyright clean; the unit file ran green (6 tests). Partial: `IntegrationHealthWorkflow` per firm (the tick that calls `apply_probe` through each install's Connect port), the `connection_needs_reauth` notification kind subscribed to the outbox event, the optional SSE topic and the replay history are not built. Gates and
  tests run once at the S47 end pass (build first, test last).
