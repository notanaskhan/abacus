---
id: TASK-7303
title: "P-10-T45: GET /v1/agents/capabilities?engagement_id= from flags, autonomy policy, boundary facts and consent, with no model call"
spec: SPEC-647
acceptance_criteria: [AC-T45]
risk_zone: red
status: in-review
branch: s37-p10-t45
worktree: /Users/ayushkbhatia/Accrued/abacus-s37
created: 2026-11-12
updated: 2026-11-12
plan_key: P-10-T45
---

## Objective
For the Stein taxpayer the tax capabilities read unavailable with reason `consent_7216` and no
usage row is written.

## Plan (red)
- `agents/capability_availability.py` (PROTECTED): installable v2 specs (TEST_ONLY only for a
  synthetic firm), reasons in order `paused`, `ai_policy_off`, `ai_excluded`, `consent_7216`,
  `not_on_team`; facts from `agents_paused`, the engagement agent's pause, the effective AI
  policy's autonomy level, `ai_excluded`, C19's `covering_consents` for the engagement's
  taxpayer and year, and `could(agent_run.start)`. No gateway call.
- Route: `runs_v2_contract.list_capabilities_route` (the T09 stub; `session.read`,
  `agent_runtime.v2`); a walled engagement answers 404 through `get_ref`.
- No migration, no flag, no new action.
- Tests: `tests/unit/agents/test_p10t45_capability_availability.py`,
  `tests/integration/agent_tests/test_p10t45_capabilities.py`.
- Rollback: revert (the route answers 501 again).

## Notes
- `issues.fix_runner` declares `tri` too (it reads return fields), so it reads `consent_7216`
  for the same taxpayer.
- An engagement with no period end reads `consent_7216` for every `tri` capability (fail closed).

## Progress log
- `2026-11-12` — Built (S37). Import smoke and ruff clean; tests written, not run (end pass).
