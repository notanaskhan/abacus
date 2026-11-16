---
id: TASK-8332
title: "W-01-T14: Agent dependency on integrations"
spec: docs/plan/epics/W-01.md F5
acceptance_criteria: [W-01-T14]
risk_zone: red
status: in-review
branch: w01-t14-agent-dependency
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: W-01-T14
---

## Objective
Agent dependency on integrations.

## Plan (red)
1. `integrations/dependents.py`: `admission_failure` (pure; codes `integration_reauth_required`, `integration_unhealthy`, `integration_not_connected`), `admit` against the firm's installs, `record_run_failed` (one `run_failed` event naming the run), `failed_runs_since`, the dependents provider slot.
2. Tests: `tests/unit/integrations/test_w01t14_dependents.py`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack (DEC-5320). Lint and pyright clean; the unit file ran green (3 tests). Partial: `requires_integrations` on the capability spec schema (spec v2, protected) and the agents module's admission call and dependents provider registration are not wired. Gates and
  tests run once at the S47 end pass (build first, test last).
