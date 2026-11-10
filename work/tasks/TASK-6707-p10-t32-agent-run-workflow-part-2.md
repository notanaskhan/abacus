---
id: TASK-6707
title: "P-10-T32: AgentRunWorkflow part 2: questions (answer, skip, skip default), decision cards through review.api, step retry as a new row, whole-run retry as a child run, redirects, stop, failure path, workflow.patched histories"
spec: SPEC-647
acceptance_criteria: [AC-W4, AC-W5, AC-W6, AC-W10]
risk_zone: red
status: in-review
branch: s35-p10-t32
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-10
updated: 2026-11-10
plan_key: P-10-T32
---

## Objective
A run blocked on the Northwind materiality card resumes only the held branch after Margaret Okonkwo decides, a retry creates a new step row, and recorded histories replay.

## Plan (red)
1. `agents/run_plan.py`: `Schedule.waiting`, `retry(key)` (queues the failed step and the steps
   its failure skipped), `replace(steps)` (a redirect's merge), `stop()`.
2. `agents/run_waits.py` (new): `open_wait` (a question or approval: one `agent_questions` row,
   step `waiting_on_inputs`, `needs = {question_id, skip_default}`; a decision: a C3 card through
   `review.api.raise_decision_card` in the agent's task scope, step `blocked`, `needs = {card_id}`),
   activities `wait_state` (reads the rows; a skip applies and records the skip default once) and
   `cancel_held`, and the `decision.decided` consumer that signals the run holding the card.
3. `agents/run_activities.py`: `execute_step` opens the wait for the three waiting kinds; a retry
   is a new row at a new `seq` with `retry_of_step_id`; `StepOutcome.wait_ref`.
4. `agents/run_workflow.py`: signals `question_answered`, `decision_decided`, `step_retry`,
   `redirected`, `stop`; part 2 behind `workflow.patched("agent-run-v2-part-2")`: the run shows
   `needs_input`/`blocked_on_decision` with `blocked_on {kind, step_seq}`, wakes on a signal and
   resumes only the held branch; a step activity failing after its retries fails its step only.
5. `agents/run_commands.py` (new): `wake`, `retry_step`, `retry_run` (a child run with
   `parent_run_id`, `trigger_kind = retry`), live person only. P-10-T33's routes call them.
6. `review.api.card_decision` (read-only; agents never reads review's tables).
7. Registry: catalogue reviewed actions; error codes `run_not_ended`, `step_not_failed`;
   `decision.decided` in agents' SUBSCRIPTIONS.
8. Histories: `abacus_tools/workflows/record_agent_run.py` (five scenarios, stub activities);
   replay test `tests/workflows/test_p10t32_agent_run_replay.py`.
9. Tests: `tests/unit/agents/test_p10t32_run_part2.py`.
10. Rollback: revert; runs started before the patch replay part 1's path.

## Partial
- Histories are recorded at the end pass (Docker stack); until then the replay test fails on
  purpose. Part 1's own histories (P-10-T29) are covered by `agent-run-v2-approved`.
- Long waits do not continue-as-new yet (a run held for weeks grows its history); noted for P-10-T33.

## Progress log
- `2026-11-10` — Built; tests written, not run (end pass).
