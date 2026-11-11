---
id: TASK-6804
title: "P-10-T39: Engagement run (engagements.run): code plan from methodology program steps with levels and depends_on, static EBP section-list fallback, register_run_step slot, POST /v1/engagements/{id}/runs, engagement_ai_settings and PUT auto-mode with effective autonomy (forced off for real firms until the capability is live)"
spec: SPEC-647
acceptance_criteria: [AC-E1, AC-E2, AC-E3, AC-E4]
risk_zone: red
status: in-review
branch: s36-p10-t39
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: P-10-T39
---

## Objective
Northwind's run projects 14 = 1 + 5 + 1 + 4 + 3 workpapers over 5 levels, holds Planning on the
materiality card, and Auto mode cannot be on for a real firm.

## Plan (red: written before the build)
1. `agents/engagement_run.py`: the code plan (pinned methodology version's levelled steps onto five
   run levels, `depends_on` kept where it points lower, a planning materiality step as the C3
   `planning_materiality` card; else the static EBP section list); `register_run_step` slot with a
   built-in `workpaper` readiness handler; `start_engagement_run` (live person, `agent_run.start`,
   409 `run_step_unavailable` before any row, row with the plan in its inputs, `AgentRunWorkflow`
   dispatched); `set_auto_mode` / `effective_auto_mode` (409 `auto_mode_not_available` for a real
   firm; effective autonomy off for a real firm whatever is stored).
2. `run_activities.execute_step`: a `run_step.<kind>` step goes to its handler (no C17 call).
3. `methodology.VersionStep.depends_on` (additive).
4. Routes `POST /v1/engagements/{id}/runs` and `PUT /v1/engagements/{id}/auto-mode` implemented
   (`errors=(409, 501)` kept).
5. Tests: `tests/unit/agents/test_p10t39_engagement_run.py`,
   `tests/integration/agent_tests/test_p10t39_engagement_run.py`.
6. Rollback: revert; `engagement_run.enabled` stays off (404).

## Progress log
- `2026-11-11` — Built (S36). Tests written, not run (end pass).

## Partials
- Auto mode on a synthetic firm marks the run `mode: auto` but the plan still waits for approval:
  skipping `awaiting_plan_approval` needs ADR-186's standing approval record (a person's, bound to
  a schedule; W-03/K-04), and the database binds plan decisions to a live person.
- The built-in `workpaper` step only checks the bound workpaper exists; preparing papers is each
  owner's handler (A-04/A-05/K-04 register theirs through `register_run_step`).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-3404 | Code plan, run-step slot, start, auto mode | no |
