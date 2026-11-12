---
id: TASK-7621
title: T-05-T31 workbook run plan on the P-10 runtime (tax.entity_workbook)
plan_key: T-05-T31
spec: SPEC-651
acceptance_criteria: [AC-F2]  # re-running the capital group runs only capital and K-1 steps; human cells kept; histories replay
risk_zone: red
status: in-review
branch: t05-t31-run-plan
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
The entity return's workbook run as P-10's engagement run on a code plan supplied by the return's
owner: ten steps in six groups, scopes all, group and task with dependants, human cells kept on a
re-run, model steps waiting on §7216 consent, at most three at once.

## Plan
- `agents/engagement_run.py` (protected): the plan-provider slot (`PlanRequest`,
  `register_plan_provider`, `plan_provider`, `PlanProviderUnavailable`); `start_engagement_run`
  takes `provider` and `request` (the plan, scope, keys and work item go into the run's inputs);
  `work_item_runs` (a work item's runs, newest first; `active` until terminal). Exports in
  `agents/api.py`.
- `tax/entity_run_plan.py` (new): the ten steps and six groups, `selected` (dependants closure,
  dependencies dropped), `plan_steps` (question step `consent_7216` for model steps without
  consent), `consent_in_force` (C19 verdict for the partnership's year), the provider registered
  at the tax api's import.
- `tax/workbook_contract.py`: `POST /v1/tax-returns/{id}/workbook-runs` (409 `run_in_progress`)
  and `GET …/workbook-runs` served.
- `tax/workbook_service.py`: `engine_may_write` (a run step never writes over a human value).
- Test `backend/tests/unit/tax/test_t05t31_entity_run_plan.py`. `make generate`.
- Rollback: revert; the routes go back to 501 and nothing else started such a run.

## Deviations (DEC-4616)
- No new workflow or patch: the plan is code supplied at start into P-10's unchanged
  `AgentRunWorkflow`, so the existing `agent-run-v2-*` histories are the replay histories.
- Consent is a question step the person answers after recording consent (the run waits on inputs);
  the step handlers (T-05-T32) re-check consent before any model call.
- Group levels are 1 to 6 (the plan validator orders dependencies by level); SHL-13's five-level
  projection is not used for entity runs (TXP-00 counts steps).

## Partial
- The ten handlers are T-05-T32 (part 1: import, map, contributions, capital and M-2, federal
  K-1s) and T-05-T40 (part 2); until a handler is registered the start answers 409
  `run_step_unavailable` naming it (fail closed).

## Progress log
- `2026-11-12` — Plan provider and routes built (DEC-4616). Tests at the S40 end pass.
