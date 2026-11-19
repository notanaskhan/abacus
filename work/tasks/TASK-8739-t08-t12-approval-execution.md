---
id: TASK-8739
title: "T-08-T12: Cohort approval with a single-use grant, SeasonSetupExecutionWorkflow and the engagement steps"
spec: SPEC-710
acceptance_criteria: [AC-5, AC-6]
risk_zone: red
status: in-review
branch: s51q-t08-t12-approval-execution
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-08-T12
---

## Objective
Finish T-08-T12 (TASK-8725): a partner or manager approves the cohort they saw (insert-only approval, single-use grant over the rows hash), the execution workflow consumes the grant and runs each executable row's steps once (system on behalf of the approver), engagements runs the engagement and assignment steps, and withdrawal is refused once a step ran.

## Plan (red)
1. season_execution.STEPS aligned to 0960's step CHECK.
2. season_execution_workflow.py (SeasonSetupExecutionWorkflow, SeasonExecInput, batch class); season_execution_service.py: approve_cohort (rows hash and manifest version seen; 409 stale_version / rows_hidden / cohort_approved; issue_grant; dispatch after commit), withdraw_cohort (execution_started; void_grant), execute_cohort (consume_grant against the full row set; FIFO behind an earlier executing cohort; steps once per row; failed steps record attempt and error code; step_unavailable without an executor), register_season_step; the engagement step (tax_compliance engagement rolled from last year's) and assignments step (add_rolled_forward_member re-checks each person).
3. Routes approve and withdraw-approval live; engagements api registers the workflow and activity and exports the slot.
4. Replay history season-exec-v1-executed.json (record_s51_season) and its test; tests/integration/test_t08t12_season_execution.py; cohorts ordered by office name (stable).

## Progress log
- `2026-11-19` — Built. The other steps (returns, binder, letter, consents, invitations) wait on their owners' executors (tax, requests, engagements' letter flow, consents, organisations' invitations) and are recorded failed step_unavailable, so a cohort reads failed until they register; a retry then runs only what is left. Progress events and the retry route are not in the contract yet. Gates and tests run once at the S51 end pass (build first, test last).
